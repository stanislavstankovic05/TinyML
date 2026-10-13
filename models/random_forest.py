from sklearn.ensemble import RandomForestRegressor

from models.base import BurstModel


class RandomForestModel(BurstModel):
    family = "random_forest"
    estimator_class = RandomForestRegressor
    settings = {"n_estimators": 100, "max_depth": 3}
    grid = {"max_depth": [1, 2, 3, 4, 5, 6, 8, 10, None], "n_estimators": [20, 50, 100, 300]}
