from sklearn.neighbors import KNeighborsRegressor

from models.base import BurstModel


class KnnModel(BurstModel):
    family = "knn"
    estimator_class = KNeighborsRegressor
    scaled = True
    settings = {"n_neighbors": 15}
    grid = {"n_neighbors": [3, 5, 9, 15, 25]}
