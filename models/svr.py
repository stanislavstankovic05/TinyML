from sklearn.svm import SVR

from models.base import BurstModel


class SvrModel(BurstModel):
    family = "svr"
    estimator_class = SVR
    scaled = True
    settings = {"kernel": "rbf", "C": 1.0}
    grid = {"kernel": ["rbf", "linear"], "C": [0.1, 1.0, 10.0]}
