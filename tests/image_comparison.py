from typing import Tuple

import cv2
import numpy as np
from scipy.stats import pearsonr


def naive_image_similarity(im1: np.ndarray, im2: np.ndarray, kernel: Tuple = (7, 7)) -> float:
    """Naive similarity of two images, represented as 2- or 3-dimensional numpy arrays.

    We first apply a Gaussian filter, then flatten the images and return Pearsson correlation.

    (Applying Gaussian filter brings some spatial information into the correlation.)
    """
    # convert to grayscale, if not yet
    if im1.ndim == 3:
        im1 = cv2.cvtColor(im1, cv2.COLOR_RGB2GRAY)
    if im2.ndim == 3:
        im2 = cv2.cvtColor(im2, cv2.COLOR_RGB2GRAY)

    im1 = cv2.GaussianBlur(im1, kernel, cv2.BORDER_DEFAULT)
    im2 = cv2.GaussianBlur(im2, kernel, cv2.BORDER_DEFAULT)

    return pearsonr(im1.flatten(), im2.flatten())[0]
