from sklearn.tree import DecisionTreeRegressor

from models.base import BurstModel


class DecisionTreeModel(BurstModel):
    family = "decision_tree"
    estimator_class = DecisionTreeRegressor
    settings = {"max_depth": 4}
    grid = {"max_depth": [1, 2, 3, 4, 5, 6, 8, None]}
