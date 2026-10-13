from sklearn.ensemble import ExtraTreesRegressor

from models.base import BurstModel


class ExtraTreesModel(BurstModel):
    family = "extra_trees"
    estimator_class = ExtraTreesRegressor
    settings = {"n_estimators": 100, "max_depth": 6}
    grid = {"max_depth": [2, 3, 4, 6, 8, 10, None], "n_estimators": [20, 50, 100, 300]}
