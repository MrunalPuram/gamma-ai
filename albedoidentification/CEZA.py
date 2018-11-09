
###################################################################################################
#
# Classifciation Evaluation Zenith Angle
#
# Copyright (C) by Andreas Zoglauer, Jasper Gan, & Joan Zhu.
# All rights reserved.
#
# Please see the file License.txt in the main repository for the copyright-notice.
#
###################################################################################################




###################################################################################################

""" TMVA imports """
import ROOT
import array
import sys

""" Tensorflow imports """
import tensorflow as tf
import numpy as np
import random
import time


###################################################################################################


class CEZA:

  """
  This class performs classification on evaulation of whether isReconstructable and isAbsorbed.
  A typical usage would look like this:

  AI = EnergyLossIdentification("Ling2.seq3.quality.root", "Results", "MLP,BDT", 1000000)
  AI.train()
  AI.test()"""


  def __init__(self, FileName, Output, Algorithm, MaxEvents, Quality):
    self.FileName = FileName
    self.OutputPrefix = Output
    self.Algorithms = Algorithm
    self.MaxEvents = MaxEvents
    self.Quality = Quality


###################################################################################################


  def train(self):
    """
    Switch between the various machine-learning libraries based on self.Algorithm
    """

    if self.Algorithms.startswith("TMVA:"):
     self.trainTMVAMethods()
    elif self.Algorithms.startswith("TF:"):
      self.trainTFMethods()
    else:
     print("ERROR: Unknown algorithm: {}".format(self.Algorithms))

    return


###################################################################################################

  def performTrain_TestSplit(self):
      return None

  def trainTFMethods(self):
    """
    Main training function that runs methods through Tensorflow library

    Returns
    -------
    bool
      True is everything went well, False in case of error
    """

    from sklearn.model_selection import train_test_split

    ###################################################################################################
    # Step 1: Reading data
    ###################################################################################################

    # Open the file
    DataFile = ROOT.TFile(self.FileName)
    if DataFile.IsOpen() == False:
      print("Error opening data file")
      return False

    # Get the data tree
    DataTree = DataFile.Get("Quality")
    if DataTree == 0:
      print("Error reading data tree from root file")
      return False

    # Reading training dataset
    DataLoader = ROOT.TMVA.DataLoader("Results")

    Branches = list(DataTree.GetListOfBranches())

    # Create a map of the branches
    VariableMap = {}

    for B in Branches:
      if B.GetName() == "EvaluationZenithAngle":
        VariableMap[B.GetName()] = array.array('i', [0])
      else:
        VariableMap[B.GetName()] = array.array('f', [0])
      DataTree.SetBranchAddress(B.GetName(), VariableMap[B.GetName()])


    AllFeatures = list(VariableMap.keys())
    AllFeatures.remove("SequenceLength")
    AllFeatures.remove("SimulationID")
    AllFeatures.remove("EvaluationIsReconstructable")
    AllFeatures.remove("EvaluationIsCompletelyAbsorbed")

    YTarget = "EvaluationZenithAngle"
    AllFeatures.remove(YTarget)


    XEventDataBranches = [B for B in Branches
          if not (B.GetName().startswith("Evaluation")
                  or B.GetName().startswith("SimulationID")
                  or B.GetName().startswith("SequenceLength"))]

    YResultBranches = [B for B in Branches
                      if B.GetName().startswith("EvaluationZenithAngle")]


    ###################################################################################################
    # Step 2: Input parameters
    ###################################################################################################
    print("Info: Preparing input parameters...")
    # Input parameters
    TotalData = min(self.MaxEvents, DataTree.GetEntries())
    print("\tTotal data: ", TotalData)

    # # Ensure TotalData evenly splittable so we can split half into training and half into testing
    # if TotalData % 2 == 1:
    #   TotalData -= 1
    TestSize = .3
    SubBatchSize = TotalData * TestSize      # num events in testing data

    NTrainingBatches = 1
    TrainingBatchSize = int(round(NTrainingBatches*(TotalData * (1-TestSize))))
    print("\tTraining Batch Size: ", TrainingBatchSize)

    NTestingBatches = 1
    TestBatchSize = int(round(NTestingBatches*SubBatchSize))
    print("\tTest Batch Size: ", TestBatchSize)

    Interrupted = False


    ###################################################################################################
    # Step 3: Construct training and testing dataset
    ###################################################################################################

    # Transform data into numpy array

    #placeholders
    X_data = np.zeros((TotalData, len(XEventDataBranches)))
    y_data = np.zeros((TotalData, len(YResultBranches)))

    for i in range(TotalData):
      # Print final progress
      if i == TotalData - 1:
        print("{}: Progress: {}/{}".format(time.time(), i + 1, TotalData))

      # Display progress throughout
      elif i % 1000 == 0:
        print("{}: Progress: {}/{}".format(time.time(), i, TotalData))

      DataTree.GetEntry(i) # ???

      NewRow = [VariableMap[feature][0] for feature in AllFeatures]
      X_data[i] = np.array(NewRow)
      y_data[i] = float(VariableMap[YTarget][0])

      # # Split half the X data into training set and half into testing set
      # if i % 2 == 0:
      #   XTrain[i // 2] = np.array(NewRow)
      #   YTrain[i // 2] =  float(VariableMap[YTarget][0])
      # else:
      #   XTest[i // 2] = np.array(NewRow)
      #   YTest[i // 2] =  float(VariableMap[YTarget][0])

    print("{}: finish formatting array".format(time.time()))


    XTrain, XTest, YTrain, YTest = train_test_split(X_data, y_data, test_size = TestSize, random_state = 42)

    ###################################################################################################
    # Setting up the neural network
    ###################################################################################################


    print("Info: Setting up Tensorflow neural network...")

    # Placeholders
    print("      ... placeholders ...")
    # shape as None = variable length of data points, NumFeatures
    X = tf.placeholder(tf.float32, [None, XTrain.shape[1]], name="X")
    Y = tf.placeholder(tf.float32, [None, YTrain.shape[1]], name="Y")
    keep_prob = tf.placeholder("float")

    # Layers: 1st hidden layer X1, 2nd hidden layer X2, etc.
    print("      ... hidden layers ...")
    H = tf.contrib.layers.fully_connected(X, 20) #, activation_fn=tf.nn.relu6, weights_initializer=tf.truncated_normal_initializer(0.0, 0.1), biases_initializer=tf.truncated_normal_initializer(0.0, 0.1))
    # H = tf.contrib.layers.fully_connected(H, 100)
    # H = tf.contrib.layers.fully_connected(H, 1000)

    print("      ... output layer ...")
    Output = tf.contrib.layers.fully_connected(H, len(YResultBranches), activation_fn=None)

    #TODO: Add Dropout to reduce overfitting

    # Loss function
    print("      ... loss function ...")
    LossFunction = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(labels=Y, logits=Output))

    # Minimizer
    print("      ... minimizer ...")
    Trainer = tf.train.AdamOptimizer().minimize(LossFunction)

    # Create and initialize the session
    print("      ... session ...")
    sess = tf.Session()
    sess.run(tf.global_variables_initializer())
    sess.run(tf.local_variables_initializer())

    print("      ... writer ...")
    writer = tf.summary.FileWriter("OUT_ToyModel2DGauss", sess.graph) # ???
    writer.close()

    # Add ops to save and restore all the variables.
    print("      ... saver ...")
    Saver = tf.train.Saver()

    ###################################################################################################
    # Training and evaluating the network
    ###################################################################################################

    print("Info: Training and evaluating the network")

    # Train the network
    Timing = time.process_time()

    TimesNoImprovement = 0
    BestError = sys.float_info.max

    def CheckPerformance():
      nonlocal TimesNoImprovement
      nonlocal BestError

      Error = sess.run(LossFunction, feed_dict={X: XTest, Y: YTest})

      print("Iteration {} - Error of test data: {}".format(Iteration, Error))

      if BestError - Error > 0.0001:
        BestError = Error
        TimesNoImprovement = 0

      else: # don't iterate if difference is too small
        TimesNoImprovement += 1

    # Main training and evaluation loop
    MaxIterations = 5000
    for Iteration in range(MaxIterations):
      # Take care of Ctrl-C
      if Interrupted == True: break

      # Train
      # for Batch in range(NTrainingBatches):
      #   if Interrupted == True: break
      #
      #   Start = Batch * SubBatchSize #SubBatchSize = TotalData * TestSize
      #   Stop = (Batch + 1) * SubBatchSize
      #   print("Start: ", Start)
      #   print("Stop: ", Stop)
      #   _, Loss = sess.run([Trainer, LossFunction], feed_dict={X: XTrain[Start:Stop], Y: YTrain[Start:Stop]})

      _, Loss = sess.run([Trainer, LossFunction], feed_dict=({X:XTrain, Y:YTrain}))

      # Check performance: Mean squared error
      if Iteration > 0 and Iteration % 200 == 0:
        CheckPerformance()
        print("Iteration {} - Error of train data: {}".format(Iteration, Loss))

      if TimesNoImprovement == 10:
        print("No improvement for 10 rounds")
        break;

    Timing = time.process_time() - Timing
    if Iteration > 0:
      print("Time per training loop: ", Timing/Iteration, " seconds")

    print("Error: " + str(BestError))

    correct_predictions_OP = tf.equal(tf.argmax(Output,1), tf.argmax(Y,1))
    accuracy_OP = tf.reduce_mean(tf.cast(correct_predictions_OP, "float"))
    print("Final accuracy on test set: %s" %str(sess.run(accuracy_OP,
                                        feed_dict={X: XTest, Y: YTest})))

    input("Press [enter] to EXIT")
    sys.exit(0)


###################################################################################################






  def trainTMVAMethods(self):
    """
    Main training function

    Returns
    -------
    bool
      True is everything went well, False in case of an error

    """
    # Open the file
    DataFile = ROOT.TFile(self.FileName)
    if DataFile.IsOpen() == False:
      print("Error opening data file")
      return False

    # Get the data tree
    DataTree = DataFile.Get("Quality")
    if DataTree == 0:
      print("Error reading data tree from root file")
      return False

    # Limit the number of events:
    if DataTree.GetEntries() > self.MaxEvents:
      print("Reducing source tree size from " + str(DataTree.GetEntries()) + " to " + str(self.MaxEvents) + " (i.e. the maximum set)")
      NewTree = DataTree.CloneTree(0);
      NewTree.SetDirectory(0);

      for i in range(0, self.MaxEvents):
        DataTree.GetEntry(i)
        NewTree.Fill()

      DataTree = NewTree;

    # Initialize TMVA
    ROOT.TMVA.Tools.Instance()

    FullPrefix = self.OutputPrefix
    ResultsFile = ROOT.TFile(FullPrefix + ".root","RECREATE")

    Factory = ROOT.TMVA.Factory("TMVAClassification", ResultsFile,
                                ":".join([
                                    "!V",
                                    "!Silent",
                                    "Color",
                                    "DrawProgressBar",
                                    "Transformations=I;D;P;G,D",
                                    "AnalysisType=Classification"]
                                         ))

    DataLoader = ROOT.TMVA.DataLoader("Results")

    IgnoredBranches = [ 'SimulationID', 'SequenceLength']  #'EvaluationZenithAngle', 'EvaluationIsReconstructable', 'EvaluationIsCompletelyAbsorbed']
    Branches = DataTree.GetListOfBranches()

    for Name in IgnoredBranches:
       DataLoader.AddSpectator(Name, "F")

    for b in list(Branches):
        if not b.GetName() in IgnoredBranches:
            if not b.GetName().startswith("Evaluation"):
                DataLoader.AddVariable(b.GetName(), "F")

    SignalCut = ROOT.TCut("EvaluationZenithAngle > 90")
    BackgroundCut = ROOT.TCut("EvaluationZenithAngle <= 90")
    DataLoader.SetInputTrees(DataTree, SignalCut, BackgroundCut)

    DataLoader.PrepareTrainingAndTestTree(SignalCut,
                                       BackgroundCut,
                                       ":".join([
                                            "nTrain_Signal=0",
                                            "nTrain_Background=0",
                                            "SplitMode=Random",
                                            "NormMode=NumEvents",
                                            "!V"
                                           ]))


    # Neural Networks
    if 'MLP' in self.Algorithms:
      method = Factory.BookMethod(DataLoader, ROOT.TMVA.Types.kMLP, "MLP",
          ":".join([
              "H:",
              "!V",
              "NeuronType=tanh",
              "VarTransform=N",
              "NCycles=100",
              "HiddenLayers=2*N,N",
              "TestRate=5",
              "!UseRegulator"
              ]))

    # PDEFoamBoost
    if 'PDEFoamBoost' in self.Algorithms:
      method = Factory.BookMethod(DataLoader, ROOT.TMVA.Types.kPDEFoam, "PDEFoamBoost",
        ":".join([
          "!H",
          "!V",
          "Boost_Num=30",
          "Boost_Transform=linear",
          "SigBgSeparate=F",
          "MaxDepth=4",
          "UseYesNoCell=T",
          "DTLogic=MisClassificationError",
          "FillFoamWithOrigWeights=F",
          "TailCut=0",
          "nActiveCells=500",
          "nBin=20",
          "Nmin=400",
          "Kernel=None",
          "Compress=T"
          ]))

    # PDERSPCA
    if 'PDERSPCA' in self.Algorithms:
      method = Factory.BookMethod(DataLoader, ROOT.TMVA.Types.kPDERS, "PDERSPCA",
          ":".join([
              "!H",
              "!V",
              "VolumeRangeMode=Adaptive",
              "KernelEstimator=Gauss",
              "GaussSigma=0.3",
              "NEventsMin=400",
              "NEventsMax=600",
              "VarTransform=PCA"
          ]))

    # Random Forest Boosted Decision Trees
    if 'BDT' in self.Algorithms:
      method = Factory.BookMethod(DataLoader, ROOT.TMVA.Types.kBDT, "BDT",
                         ":".join([
                             "!H",
                             "!V",
                             "NTrees=850",
                             "nEventsMin=150",
                             "MaxDepth=3",
                             "BoostType=AdaBoost",
                             "AdaBoostBeta=0.5",
                             "SeparationType=GiniIndex",
                             "nCuts=20",
                             "PruneMethod=NoPruning",
                             ]))

    # Finally test, train & Algorithm all methods
    Factory.TrainAllMethods()
    Factory.TestAllMethods()
    Factory.EvaluateAllMethods()



    reader = ROOT.TMVA.Reader("!Color:!Silent");
    variablemap = {}

    for Name in IgnoredBranches:
      variablemap[Name] = array.array('f', [0])
      DataTree.SetBranchAddress(Name, variablemap[Name])
      reader.AddSpectator(Name, variablemap[Name])

    for B in list(Branches):
      if not B.GetName() in IgnoredBranches:
        if not B.GetName().startswith("Evaluation"):
          variablemap[B.GetName()] = array.array('f', [0])
          reader.AddVariable(B.GetName(), variablemap[B.GetName()])
          DataTree.SetBranchAddress(B.GetName(), variablemap[B.GetName()])
          print("Added: " + B.GetName())

    for B in list(Branches):
      if B.GetName().startswith("EvaluationZenithAngle"):
        variablemap[B.GetName()] = array.array('f', [0])
        DataTree.SetBranchAddress(B.GetName(), variablemap[B.GetName()])


    # TODO: loop over different readers that call different methods and output best one
    Algorithm = ''
    if 'MLP' in self.Algorithms:
      Algorithm = 'MLP'
      reader.BookMVA("MLP","Results/weights/TMVAClassification_MLP.weights.xml")
    elif 'BDT' in self.Algorithms:
      Algorithm = 'BDT'
      reader.BookMVA("BDT","Results/weights/TMVAClassification_BDT.weights.xml")
    elif 'PDEFoamBoost' in self.Algorithms:
      Algorithm = 'PDEFoamBoost'
      reader.BookMVA("PDEFoamBoost","Results/weights/TMVAClassification_PDEFoamBoost.weights.xml")
    elif 'PDERSPCA' in self.Algorithms:
      Algorithm = 'PDERSPCA'
      reader.BookMVA("PDERSPCA","Results/weights/TMVAClassification_PDERSPCA.weights.xml")

    NEvents = 0
    NGoodEvents = 0

    NLearnedGoodEvents = 0
    NLearnedCorrectEvents = 0

    varx = array.array('f',[0]) #; reader.AddVariable("EvaluationZenithAngle",varx)
    vary = array.array('f',[0]) #; reader.AddVariable("result",vary)

    for x in range(0, min(100, DataTree.GetEntries())):
      DataTree.GetEntry(x)

      NEvents += 1

      print("\nSimulation ID: " + str(int(variablemap["SimulationID"][0])) + ":")

      result = reader.EvaluateMVA(Algorithm)
      vary.append(result)

      r = 2
      IsGood = True
      IsGoodThreshold = 0.2

      IsLearnedGood = True
      IsLearnedGoodThreshold = 0.06 # Adjust this as see fit

      for b in list(Branches):
        Name = b.GetName()

        if Name.startswith("EvaluationZenithAngle"):
          print(Name + " " + str(variablemap[Name][0]) + " vs. " + str(90))
          varx.append(variablemap[Name][0])
          if abs(variablemap[Name][0] - 90 > IsGoodThreshold):
            IsGood = False
          r += 1

      if IsGood == True:
        NGoodEvents += 1
        print(" --> Good event")
      else:
        print(" --> Bad event")

      if (IsLearnedGood == True and IsGood == True) or (IsLearnedGood == False and IsGood == False):
        NLearnedCorrectEvents += 1

    print("\nResult:")
    print("All events: " + str(NEvents))
    print("Good events: " + str(NGoodEvents))
    print("Correctly identified: " + str(NLearnedCorrectEvents / NEvents))

    ### Graph Results (y-axis) on EvaluationZenithAngle (x-axis)

    # Visualizing the performance:

    # keeps objects otherwise removed by garbage collected in a list
    gcSaver = []

    # create a new TCanvas
    gcSaver.append(ROOT.TCanvas())

    # create a new 2D histogram with fine binning
    histo2 = ROOT.TH2F("histo2","",200,-5,5,200,-5,5)

    # loop over the bins of a 2D histogram
    for i in range(1,histo2.GetNbinsX() + 1):
        for j in range(1,histo2.GetNbinsY() + 1):

            # find the bin center coordinates
            varx[0] = histo2.GetXaxis().GetBinCenter(i)
            vary[0] = histo2.GetYaxis().GetBinCenter(j)

            # calculate the value of the classifier
            # function at the given coordinate
            bdtOutput = reader.EvaluateMVA(Algorithm)

            # set the bin content equal to the classifier output
            histo2.SetBinContent(i,j,bdtOutput)

    gcSaver.append(ROOT.TCanvas())
    histo2.Draw("colz")

    # draw sigma contours around means
    for mean, color in (
        ((1,1), ROOT.kRed), # signal
        ((-1,-1), ROOT.kBlue), # background
        ):

        # draw contours at 1 and 2 sigmas
        for numSigmas in (1,2):
            circle = ROOT.TEllipse(mean[0], mean[1], numSigmas)
            circle.SetFillStyle(0)
            circle.SetLineColor(color)
            circle.SetLineWidth(2)
            circle.Draw()
            gcSaver.append(circle)

    ROOT.TestTree.Draw(Algorithm + ">>hSig(22,-1.1,1.1)","classID == 0","goff")  # signal
    ROOT.TestTree.Draw(Algorithm + ">>hBg(22,-1.1,1.1)","classID == 1", "goff")  # background

    ROOT.hSig.SetLineColor(ROOT.kRed); ROOT.hSig.SetLineWidth(2)  # signal histogram
    ROOT.hBg.SetLineColor(ROOT.kBlue); ROOT.hBg.SetLineWidth(2)   # background histogram

    # use a THStack to show both histograms
    hs = ROOT.THStack("hs","")
    hs.Add(ROOT.hSig)
    hs.Add(ROOT.hBg)

    # show the histograms
    gcSaver.append(ROOT.TCanvas())
    hs.Draw()

    # prevent Canvases from closing
    print("Close the ROOT window via File -> Close!")
    ROOT.gApplication.Run()


###################################################################################################


  def test(self):
    """
    Main test function

    Returns
    -------
    bool
      True is everything went well, False in case of an error

    """

    return True


# END
###################################################################################################
