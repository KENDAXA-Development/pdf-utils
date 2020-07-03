from typing import Tuple

import numpy as np
from scipy.stats import pearsonr
import cv2


def naive_image_similarity(im1: np.ndarray, im2: np.ndarray, kernel:Tuple = (7, 7)):
    """Naive similarity of two images.

    We first apply a Gaussian filter, then flatten the images and return Pearsson correlation.

    (Applying Gaussian filter brings some spatial information into the correlation.)
    """
    im1 = cv2.GaussianBlur(im1, kernel, cv2.BORDER_DEFAULT)
    im2 = cv2.GaussianBlur(im2, kernel, cv2.BORDER_DEFAULT)
    return pearsonr(im1.flatten(), im2.flatten())[0]
