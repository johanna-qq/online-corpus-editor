# Online Corpus Editor: Language Identification
# Uses nltk's MaxEnt classifier with MEGAM

import os
import pickle
import sys

import nltk.classify
import nltk.tokenize

import oce.util
import oce.logger
import oce.langid.features

logger = oce.logger.getLogger(__name__)

# === Config ===
from oce.config import default_model, default_trained_file


class LangIDController:
    def __init__(self, model=default_model, trained_file=default_trained_file):
        self.model = model
        self.trained_file = trained_file

        # === Classifier ===
        self.classifier = self.load_classifier(trained_file)
        if self.classifier is not None:
            if not hasattr(self.classifier, 'model_name'):
                print("The loaded classifier does not specify which model it "
                      "uses; it could be different from the one expected.  "
                      "Use .train_classifier() followed by .save_classifier() "
                      "to overwrite it.")
            elif self.classifier.model_name != model:
                print("The model used by the loaded classifier (" +
                      self.classifier.model_name +
                      ") is different from the one requested (" +
                      model +
                      ").  "
                      "Use .train_classifier() followed by .save_classifier() "
                      "to overwrite it.")
        else:
            logger.warning("No previously trained classifier found. (" +
                           trained_file + ")")
            logger.warning("Use .train_classifier() and .save_classifier() to "
                           "train and save a new classifier respectively.")

        logger.info("Language ID module initialised.")

    def load_classifier(self, trained_file):
        try:
            f = open(trained_file, 'rb')
            classifier = pickle.load(f)
            f.close()
            print("Loaded previously trained classifier. (" +
                  trained_file + ")")
            return classifier
        except FileNotFoundError:
            return None

    def save_classifier(self, trained_file=None):
        classifier = self.get_classifier()
        if classifier is None:
            logger.warning("Could not save classifier. (None currently "
                           "initialised.)")
            return

        if trained_file is None:
            trained_file = self.trained_file
        f = open(trained_file, 'wb')
        pickle.dump(self.classifier, f)
        f.close()
        logger.info("Saved trained classifier to '" + trained_file + "'.")
        return

    def check_classifier(self):
        if isinstance(self.classifier, nltk.classify.api.ClassifierI):
            return True
        else:
            return False

    def get_classifier(self):
        if self.check_classifier():
            return self.classifier
        else:
            logger.warning("Classifier not initialised yet: Train one using "
                           ".train_classifier() first.")
            return None

    def train_classifier(self, train_set, model=default_model):
        if model == "maxent":
            model_class = nltk.classify.MaxentClassifier
            try:
                # Try to use the precompiled megam binaries
                if sys.platform.startswith("darwin"):
                    nltk.config_megam(os.path.join(".", "lib",
                                                   "megam.opt.darwin"))
                elif sys.platform.startswith("win32"):
                    nltk.config_megam(os.path.join(".", "lib",
                                                   "megam.opt.win32.exe"))
                self.classifier = model_class.train(train_set, "megam")
            except LookupError as e:
                self.classifier = model_class.train(train_set)
                msg = "Could not find Megam; Trained classifier using default " \
                      "algorithm instead.  (Much slower)\n"
                logger.warning(msg)
                msg += "\nOriginal LookupError:\n"
                custom = oce.util.CustomError(str(e).strip(), pre=msg)
                raise custom
        else:
            logger.warning("'" + model + "' is not a valid classifier model.")
            return

        self.classifier.model_name = model

    def suggest_language(self, sentence):
        classifier = self.get_classifier()
        return classifier.classify(self.extract_features(sentence))

    def prepare_labelled_data(self, raw_data):
        """
        Given some information from the db, converts into a list of tuples:
        [(<content>, <standardised label>), ...]
        :param raw_data:
        :return:
        """
        labelled_data = [(datum['content'], datum['language'])
                         for datum in raw_data]
        return labelled_data

    def extract_features(self, sentence):
        return oce.langid.features.extract_features(sentence)

    def debug(self, str):
        """
        Do arbitrary stuff with the content of a record.
        :param str:
        :return:
        """
        classifier = self.get_classifier()
        classifier.show_most_informative_features()
        print(nltk.tokenize.word_tokenize(str))

    def shutdown(self):
        logger.info("Saving trained classifier.")
        if self.check_classifier():
            self.save_classifier()
        return
