import logging
import os.path
import re
import shutil
import sys
import textwrap
from collections import OrderedDict
from io import StringIO
from itertools import chain
from pprint import pformat
from string import Template


# fixme returning MatAllocator (trait) by reference is bad, check knearestneighbour
# fixme consume arg for by_ptr settable properties
# fixme field comments //! in the end are transferred to the next field

def template(text):
    """
    :type text: str
    :rtype: Template
    """
    if len(text) > 0 and text[0] == "\n":
        text = text[1:]
    return Template(textwrap.dedent(text))


def indent(text, level=1, chars_per_level=4, char=" "):
    """
    :type text: str
    :type level: int
    :type chars_per_level: int
    :type char: str
    :rtype: str
    """
    padding = char * (level * chars_per_level)
    return padding.join(chain(("",), text.splitlines(True)))


def combine_dicts(src, add):
    out = src.copy()
    out.update(add)
    return out


def classes_equal(first, second):
    """
    :type first: str
    :type second: str
    :rtype: bool
    """
    first = first.strip()
    second = second.strip()
    if first == second:
        return True
    if not first.startswith("::") and second.endswith("::" + first):
        return True
    if not second.startswith("::") and first.endswith("::" + second):
        return True
    return False


def write_exc(filename, action):
    """ Calls action with file handle of filename only when file didn't exist before, thread-safe """
    try:
        with os.fdopen(os.open(filename, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o666), "w") as f:
            action(f)
    except OSError:
        pass


#
#       EXCEPTIONS TO AUTO GENERATION
#


# dict of decls to inject before doing header parsing
# key: module name
# value: list of declarations as supplied by hdr_parser
decls_manual_pre = {
    "core": [
        ("class cv.Range", "", ["/Ghost"], []),
        ("class cv.Mat", "", ["/Ghost"], []),
        ("class cv.Algorithm", "", ["/Ghost"], []),
        ("class cv.DMatch", "", ["/Ghost", "/Simple"], []),
        ("class cv.KeyPoint", "", ["/Ghost", "/Simple"], []),
        ("class cv.RotatedRect", "", ["/Ghost"], []),
        ("class cv.TermCriteria", "", ["/Ghost"], []),
    ],
    "dnn": [
        ("class cv.dnn.LayerParams", "", ["/Ghost"], []),
    ],
}

# dict of decls to inject after doing header parsing
# key: module name
# value: list of declarations as supplied by hdr_parser
decls_manual_post = {
    "core": [
        ("cv.Mat.size", "Size", ["/C"], []),
    ],
    "dnn": [
        ("cv.dnn.LayerParams.LayerParams", "", [], []),
    ],
}

# dict of functions to rename or skip, key is FuncInfo.identifier, value is new name ("+" will be replaces by old name) or "-" to skip
func_rename = {  # todo check if any "new" is required
    # fixme remove entries that don't actually change name
    ### calib3d ###
    "cv_findEssentialMat_Mat_Mat_Mat_int_double_double_Mat": "+_matrix",
    "cv_findHomography_Mat_Mat_int_double_Mat_int_double": "+_full",
    "cv_fisheye_projectPoints_Mat_Mat_Mat_Mat_Mat_Mat_double_Mat": "fisheye_+",
    "cv_fisheye_undistortImage_Mat_Mat_Mat_Mat_Mat_Size": "fisheye_+",
    "cv_fisheye_undistortPoints_Mat_Mat_Mat_Mat_Mat_Mat": "fisheye_+",
    "cv_recoverPose_Mat_Mat_Mat_Mat_Mat_Mat_Mat": "+_camera_with_points",
    "cv_recoverPose_Mat_Mat_Mat_Mat_Mat_Mat_double_Mat_Mat": "+_camera",
    "cv_solvePnP_Mat_Mat_Mat_Mat_Mat_Mat_bool_int": "solve_pnp",
    "cv_solvePnPRansac_Mat_Mat_Mat_Mat_Mat_Mat_bool_int_float_double_Mat_int": "solve_pnp_ransac",
    "cv_solveP3P_Mat_Mat_Mat_Mat_VectorOfMat_VectorOfMat_int": "solve_p3p",
    "cv_calibrateCamera_VectorOfMat_VectorOfMat_Size_Mat_Mat_VectorOfMat_VectorOfMat_Mat_Mat_Mat_int_TermCriteria": "+_with_stddev",
    "cv_stereoCalibrate_VectorOfMat_VectorOfMat_VectorOfMat_Mat_Mat_Mat_Mat_Size_Mat_Mat_Mat_Mat_int_TermCriteria": "+_camera",
    "cv_stereoCalibrate_VectorOfMat_VectorOfMat_VectorOfMat_Mat_Mat_Mat_Mat_Size_Mat_Mat_Mat_Mat_Mat_int_TermCriteria": "+_camera_with_errors",
    "cv_stereoRectify_Mat_Mat_Mat_Mat_Size_Mat_Mat_Mat_Mat_Mat_Mat_Mat_int_double_Size_Rect_X_Rect_X": "+_camera",
    "cv_findFundamentalMat_Mat_Mat_int_double_double_Mat": "-",  # duplicate of cv_findFundamentalMat_Mat_Mat_Mat_int_double_double, but with different order of arguments

    ### core ###
    "cv_addImpl_int_const_char_X": "-",
    "cv_MatExpr_type_const": "typ",
    "cv_Mat_Mat_int_int_int": "new_rows_cols",
    "cv_Mat_Mat_Size_int": "new_size",
    "cv_Mat_Mat_int_int_int_Scalar": "new_rows_cols_with_default",
    "cv_Mat_Mat_Size_int_Scalar": "new_size_with_default",
    "cv_Mat_Mat_int_const_int_X_int": "-",  # duplicate of cv_Mat_Mat_VectorOfint_int, but with pointers
    "cv_Mat_Mat_VectorOfint_int": "new_nd",
    "cv_Mat_Mat_int_const_int_X_int_Scalar": "-",  # duplicate of cv_Mat_Mat_VectorOfint_int_Scalar_s, but with pointers
    "cv_Mat_Mat_VectorOfint_int_Scalar": "new_nd_with_default",
    "cv_Mat_Mat_Mat": "copy",
    "cv_Mat_Mat_int_int_int_void_X_size_t": "new_rows_cols_with_data",
    "cv_Mat_Mat_Size_int_void_X_size_t": "new_size_with_data",
    "cv_Mat_Mat_int_const_int_X_int_void_X_const_size_t_X": "-",  # duplicate of cv_Mat_Mat_VectorOfint_int_void_X_const_size_t_X, but with pointers
    "cv_Mat_Mat_VectorOfint_int_void_X_const_size_t_X": "new_nd_with_data",  # fixme steps should be slice
    "cv_Mat_Mat_Mat_Range_Range": "rowscols",
    "cv_Mat_Mat_Mat_Rect": "roi",
    "cv_Mat_Mat_Mat_const_Range": "-",  # duplicate of cv_Mat_Mat_Mat_VectorOfRange_ranges, but with pointers
    "cv_Mat_Mat_Mat_VectorOfRange": "ranges",
    "cv_Mat_colRange_const_Range": "colrange",
    "cv_Mat_colRange_const_int_int": "colbounds",
    "cv_Mat_copyTo_const_Mat_Mat": "copy_to_masked",
    "cv_Mat_create_int_int_int": "create_rows_cols",
    "cv_Mat_create_Size_int": "create_size",
    "cv_Mat_create_int_const_int_X_int": "-",  # duplicate of cv_Mat_create_VectorOfint_int, but with pointers
    "cv_Mat_create_VectorOfint_int": "create_nd",
    "cv_Mat_diag_Mat": "diag_new_mat",
    "cv_Mat_ptr_int": "ptr_mut",
    "cv_Mat_ptr_int_int": "ptr_2d_mut",
    "cv_Mat_ptr_const_int_int": "ptr_2d",
    "cv_Mat_ptr_int_int_int": "ptr_3d_mut",
    "cv_Mat_ptr_const_int_int_int": "ptr_3d",
    "cv_Mat_ptr_const_int_X": "ptr_nd_mut",
    "cv_Mat_ptr_const_const_int_X": "ptr_nd",
    "cv_Mat_at_int": "at_mut",
    "cv_Mat_at_int_int": "at_2d_mut",
    "cv_Mat_at_const_int_int": "at_2d",
    "cv_Mat_at_int_int_int": "at_3d_mut",
    "cv_Mat_at_const_int_int_int": "at_3d",
    "cv_Mat_resize_size_t_Scalar": "resize_with_default",
    "cv_Mat_rowRange_const_int_int": "rowbounds",
    "cv_Mat_type_const": "typ",
    "cv_Mat_reshape_const_int_int_const_int_X": "-",  # duplicate of cv_Mat_reshape_const_int_VectorOfint, but with pointers
    "cv_Mat_reshape_const_int_VectorOfint": "reshape_nd",
    "cv_Mat_total_const_int_int": "total_slice",
    "cv_Mat_size": "-",  # doesn't have any use, dims() and Size are already accessible through other methods
    "cv_Mat_set_size_MatSize": "-",  # -"-
    "cv_Mat_set_step_MatStep": "-",  # doesn't allow writing
    "cv_merge_const_Mat_size_t_Mat": "-",  # duplicate of cv_merge_VectorOfMat_Mat, but with pointers
    "cv_Matx_TOp_Matx_TOp_Matx_TOp": "copy",
    "cv_Matx_ScaleOp_Matx_ScaleOp_Matx_ScaleOp": "copy",
    "cv_Matx_MulOp_Matx_MulOp_Matx_MulOp": "copy",
    "cv_Matx_DivOp_Matx_DivOp_Matx_DivOp": "copy",
    "cv_Matx_AddOp_Matx_AddOp_Matx_AddOp": "copy",
    "cv_Matx_SubOp_Matx_SubOp_Matx_SubOp": "copy",
    "cv_Matx_MatMulOp_Matx_MatMulOp_Matx_MatMulOp": "copy",
    "cv_PCA_PCA": "default",
    "cv_PCA_PCA_Mat_Mat_int_double": "new_mat_variance",
    "cv_PCA_PCA_Mat_Mat_int_int": "new_mat_max",
    "cv_PCA_backProject_const_Mat_Mat": "+_to",
    "cv_PCA_project_const_Mat_Mat": "+_to",
    "cv_PCACompute_Mat_Mat_Mat_double": "pca_compute_variance",
    "cv_PCACompute_Mat_Mat_Mat_Mat_double": "pca_compute_values_variance",
    "cv_PCACompute_Mat_Mat_Mat_Mat_int": "pca_compute_values",
    "cv_Range_Range": "default",
    "cv_Range_Range_int_int": "new",
    "cv_RotatedRect_RotatedRect": "default",
    "cv_RotatedRect_RotatedRect_Point2f_Point2f_Point2f": "for_points",
    "cv_TermCriteria_TermCriteria": "default",
    "cv_UMat_type_const": "typ",
    "cv_UMat_copyTo_const_Mat": "copy_to",
    "cv_UMat_copyTo_const_Mat_Mat": "copy_to_masked",
    "cv_calcCovarMatrix_const_Mat_int_Mat_Mat_int_int": "-",  # duplicate of cv_calcCovarMatrix_Mat_Mat_Mat_int_int, but with pointers
    "cv_clipLine_Size_Point_Point": "clip_line_size",
    "cv_clipLine_Size2l_Point2l_Point2l": "clip_line_size_i64",
    "cv_clipLine_Rect_Point_Point": "clip_line",
    "cv_cv_abs_short": "-",
    "cv_cv_abs_uchar": "-",
    "cv_divide_Mat_Mat_Mat_double_int": "divide_mat",
    "cv_ellipse_Mat_RotatedRect_Scalar_int_int": "ellipse_new_rotated_rect",
    "cv_ellipse2Poly_Point2d_Size2d_int_int_int_int_VectorOfPoint2d": "ellipse_2_poly_f64",
    "cv_ellipse2Poly_Point_Size_int_int_int_int_VectorOfPoint": "ellipse_2_poly",
    "cv_norm_Mat_Mat_int_Mat": "norm_with_type",
    "cv_rectangle_Mat_Point_Point_Scalar_int_int_int": "rectangle_points",
    "cv_repeat_Mat_int_int_Mat": "repeat_to",
    "cv_split_Mat_Mat": "-",  # duplicate of cv_split_Mat_VectorOfMat, but with pointers
    "cv_getNumberOfCPUs": "get_number_of_cpus",
    "cv_setImpl_int": "-",
    "cv_setUseCollection_bool": "-",
    "cv_useCollection": "-",
    "cv_directx_getTypeFromD3DFORMAT_int": "get_type_from_d3d_format",
    "cv_divUp_size_t_unsigned_int": "duv_up_u",
    "cv_hconcat_Mat_Mat_Mat": "hconcat_2",
    "cv_hconcat_const_Mat_size_t_Mat": "-",  # duplicate of cv_hconcat_VectorOfMat_Mat, but with pointers
    "cv_vconcat_Mat_Mat_Mat": "vconcat_2",
    "cv_vconcat_const_Mat_size_t_Mat": "-",  # duplicate of cv_vconcat_VectorOfMat_Mat, but with pointers
    "cv_Cholesky_float_X_size_t_int_float_X_size_t_int": "cholesky_f32",
    "cv_LU_float_X_size_t_int_float_X_size_t_int": "lu_f32",
    "cv_LDA_LDA_VectorOfMat_Mat_int": "new_with_data",
    "cv_mixChannels_VectorOfMat_VectorOfMat_const_int_X_size_t": "-",  # duplicate of cv_mixChannels_VectorOfMat_VectorOfMat_VectorOfint, but with pointers
    "cv_mixChannels_const_Mat_size_t_Mat_size_t_const_int_X_size_t": "-",  # duplicate of cv_mixChannels_VectorOfMat_VectorOfMat_VectorOfint, but with pointers
    "cv_noArray": "-",  # fixme: conversion from ‘const cv::_InputOutputArray’ to non-scalar type ‘cv::Mat’ requested

    ### features2d ###
    "cv_AGAST_Mat_VectorOfKeyPoint_int_bool": "AGAST",
    "cv_AGAST_Mat_VectorOfKeyPoint_int_bool_int": "AGAST_with_type",
    "cv_BOWKMeansTrainer_cluster_const": "default",
    "cv_BOWKMeansTrainer_cluster_const_Mat": "new",
    "cv_BOWKMeansTrainer_BOWKMeansTrainer_int_TermCriteria_int_int": "new_with_criteria",
    "cv_BOWImgDescriptorExtractor_compute_Mat_VectorOfKeyPoint_Mat_VectorOfVectorOfint_Mat": "compute_desc",
    "cv_DMatch_DMatch": "default",
    "cv_DMatch_DMatch_int_int_int_float": "new_index",
    "cv_DescriptorMatcher_knnMatch_const_Mat_Mat_VectorOfVectorOfDMatch_int_Mat_bool": "knn_train_matches",
    "cv_DescriptorMatcher_knnMatch_Mat_VectorOfVectorOfDMatch_int_VectorOfMat_bool": "knn_matches",
    "cv_DescriptorMatcher_match_Mat_VectorOfDMatch_VectorOfMat": "matches",
    "cv_DescriptorMatcher_match_const_Mat_Mat_VectorOfDMatch_Mat": "train_matches",
    "cv_DescriptorMatcher_radiusMatch_const_Mat_Mat_VectorOfVectorOfDMatch_float_Mat_bool": "train_radius_matches",
    "cv_DescriptorMatcher_radiusMatch_Mat_VectorOfVectorOfDMatch_float_VectorOfMat_bool": "radius_matches",
    "cv_FAST_Mat_VectorOfKeyPoint_int_bool": "FAST",
    "cv_FAST_Mat_VectorOfKeyPoint_int_bool_int": "FAST_with_type",
    "cv_Feature2D_detect_VectorOfMat_VectorOfVectorOfKeyPoint_VectorOfMat": "+_multiple",
    "cv_KeyPoint_KeyPoint": "default",
    "cv_KeyPoint_KeyPoint_Point2f_float_float_float_int_int": "new_point",
    "cv_KeyPoint_KeyPoint_float_float_float_float_float_int_int": "new_coords",
    "cv_KeyPoint_convert_VectorOfKeyPoint_VectorOfPoint2f_VectorOfint": "convert_from",
    "cv_KeyPoint_convert_VectorOfPoint2f_VectorOfKeyPoint_float_float_int_int": "convert_to",
    "cv_MatStep_MatStep": "default",
    "cv_drawMatches_Mat_VectorOfKeyPoint_Mat_VectorOfKeyPoint_VectorOfDMatch_Mat_Scalar_Scalar_VectorOfchar_int": "draw_matches",
    "cv_drawMatches_Mat_VectorOfKeyPoint_Mat_VectorOfKeyPoint_VectorOfVectorOfDMatch_Mat_Scalar_Scalar_VectorOfVectorOfchar_int": "draw_vector_matches",
    "cv_BRISK_create_VectorOffloat_VectorOfint_float_float_VectorOfint": "create_with_pattern",
    "cv_BRISK_create_int_int_VectorOffloat_VectorOfint_float_float_VectorOfint": "create_with_pattern_threshold_octaves",
    "cv_BOWTrainer_cluster_const_Mat": "cluster_with_descriptors",
    "cv_GFTTDetector_create_int_double_double_int_int_bool_double": "+_with_gradient",
    "cv_Feature2D_compute_VectorOfMat_VectorOfVectorOfKeyPoint_VectorOfMat": "+_multiple",
    "cv_DescriptorMatcher_create_int": "+_with_matcher_type",
    "cv_BOWImgDescriptorExtractor_BOWImgDescriptorExtractor_PtrOfFeature2D_PtrOfDescriptorMatcher": "new_with_dextractor",

    ### highgui ###
    "cv_addText_Mat_String_Point_QtFont": "+_with_font",
    "cv_selectROIs_String_Mat_VectorOfRect_bool_bool": "select_rois",
    "cv_selectROI_String_Mat_bool_bool": "+_for_window",

    ### imgcodecs ###
    "cv_imdecode_Mat_int_Mat": "+_to",

    ### imgproc ###
    "cv_Canny_Mat_Mat_Mat_double_double_bool": "+_derivative",
    "cv_Moments_Moments": "default",
    "cv_Subdiv2D_Subdiv2D": "default",
    "cv_Subdiv2D_insert_VectorOfPoint2f": "+_multiple",
    "cv_findContours_Mat_VectorOfMat_Mat_int_int_Point": "+_with_hierarchy",
    "cv_distanceTransform_Mat_Mat_Mat_int_int_int": "+_labels",
    "cv_integral_Mat_Mat_Mat_Mat_int_int": "+_titled_sq",
    "cv_integral_Mat_Mat_Mat_int_int": "+_sq_depth",
    "cv_GeneralizedHough_detect_Mat_Mat_Mat_Mat_Mat": "+_with_edges",
    "cv_goodFeaturesToTrack_Mat_Mat_int_double_double_Mat_int_int_bool_double": "+_with_gradient",

    ### ml ###
    "cv_ml_ParamGrid_ParamGrid_double_double_double": "for_range",

    ### objdetect ###
    "cv_CascadeClassifier_CascadeClassifier": "default",
    "cv_CascadeClassifier_detectMultiScale_Mat_VectorOfRect_VectorOfint_VectorOfdouble_double_int_int_Size_Size_bool": "detect_multi_scale_levels",
    "cv_CascadeClassifier_detectMultiScale_Mat_VectorOfRect_VectorOfint_double_int_int_Size_Size": "detect_multi_scale_num",
    "cv_CascadeClassifier_detectMultiScale_Mat_VectorOfRect_double_int_int_Size_Size": "detect_multi_scale",
    "cv_HOGDescriptor_HOGDescriptor_HOGDescriptor": "copy",
    "cv_HOGDescriptor_detectMultiScale_const_Mat_VectorOfRect_VectorOfdouble_double_Size_Size_double_double_bool": "detect_multi_scale",
    "cv_HOGDescriptor_detectMultiScale_const_Mat_VectorOfRect_double_Size_Size_double_double_bool": "detect_multi_scale_weights",
    "cv_HOGDescriptor_detect_const_Mat_VectorOfPoint_VectorOfdouble_double_Size_Size_VectorOfPoint": "detect_weights",
    "cv_groupRectangles_VectorOfRect_VectorOfint_VectorOfdouble_int_double": "+_levels",
    "cv_groupRectangles_VectorOfRect_VectorOfint_int_double": "+_weights",
    "cv_groupRectangles_VectorOfRect_int_double_VectorOfint_VectorOfdouble": "+_levelweights",
    "cv_ml_StatModel_train_PtrOfTrainData_int": "+_with_data",
    "cv_BaseCascadeClassifier_detectMultiScale_Mat_VectorOfRect_VectorOfint_double_int_int_Size_Size": "+_num",
    "cv_BaseCascadeClassifier_detectMultiScale_Mat_VectorOfRect_VectorOfint_VectorOfdouble_double_int_int_Size_Size_bool": "+_levels",
    "cv_HOGDescriptor_setSVMDetector_Mat": "+_mat",

    ### photo ###
    "cv_fastNlMeansDenoisingColored_Mat_Mat_float_float_int_int": "fast_nl_means_denoising_color",
    "cv_fastNlMeansDenoising_Mat_Mat_VectorOffloat_int_int_int": "fast_nl_means_denoising_vec",
    "cv_fastNlMeansDenoising_Mat_Mat_float_int_int": "fast_nl_means_denoising_window",
    "cv_AlignMTB_process_VectorOfMat_VectorOfMat_Mat_Mat": "process_with_response",
    "cv_MergeDebevec_process_VectorOfMat_Mat_Mat_Mat": "process_with_response",
    "cv_MergeMertens_process_VectorOfMat_Mat_Mat_Mat": "process_with_response",
    "cv_MergeRobertson_process_VectorOfMat_Mat_Mat_Mat": "process_with_response",

    ### video ###
    "cv_KalmanFilter_KalmanFilter": "default",

    ### videoio ###
    "cv_VideoCapture_VideoCapture": "default",
    "cv_VideoCapture_VideoCapture_int_int": "new_with_backend",
    "cv_VideoCapture_VideoCapture_String": "new_from_file",
    "cv_VideoCapture_VideoCapture_String_int": "new_from_file_with_backend",
    "cv_VideoCapture_open_int_int": "open_with_backend",
    "cv_VideoCapture_open_String": "open_file",
    "cv_VideoCapture_open_String_int": "open_file_with_backend",
    "cv_VideoWriter_VideoWriter": "default",
    "cv_VideoWriter_VideoWriter_String_int_int_double_Size_bool": "new_with_backend",
    "cv_VideoWriter_open_String_int_int_double_Size_bool": "open_with_backend",

    ### utility ###
    "cv_getImpl_VectorOfint_VectorOfString": "-",

    ### dnn ###
    "cv_dnn_<unnamed>_is_neg_int": "-",
    "cv_dnn_NMSBoxes_VectorOfRotatedRect_VectorOffloat_float_float_VectorOfint_float_int": "nms_boxes_rotated",
    "cv_dnn_NMSBoxes_VectorOfRect2d_VectorOffloat_float_float_VectorOfint_float_int": "nms_boxes_f64",
    "cv_dnn_Dict_ptr_String": "ptr_mut",
    "cv_dnn_Net_forward_VectorOfMat_String": "forward_layer",
    "cv_dnn_Net_forward_VectorOfMat_VectorOfString": "forward_first_outputs",
    "cv_dnn_Net_forward_VectorOfVectorOfMat_VectorOfString": "forward_all",
    "cv_dnn_slice_Mat_Range": "slice_1d",
    "cv_dnn_slice_Mat_Range_Range": "slice_2d",
    "cv_dnn_slice_Mat_Range_Range_Range": "slice_3d",
    "cv_dnn_slice_Mat_Range_Range_Range_Range": "slice_4d",
    "cv_dnn_shape_const_int_X_int": "shape_nd",
    "cv_dnn_shape_int_int_int_int": "shape_3d",
    "cv_dnn_blobFromImage_Mat_Mat_double_Size_Scalar_bool_bool_int": "blob_from_image_to",
    "cv_dnn_clamp_Range_int": "clamp_range",
    "cv_dnn_Net_connect_String_String": "connect_first_second",
    "cv_dnn_Layer_finalize_VectorOfMat_VectorOfMat": "finalize_to",
    "cv_dnn_readNetFromCaffe_VectorOfuchar_VectorOfuchar": "read_net_from_caffe_buffer",
    "cv_dnn_readNetFromCaffe_const_char_X_size_t_const_char_X_size_t": "read_net_from_caffe_str",
    "cv_dnn_readNetFromTensorflow_VectorOfuchar_VectorOfuchar": "read_net_from_tensorflow_buffer",
    "cv_dnn_readNetFromTensorflow_const_char_X_size_t_const_char_X_size_t": "read_net_from_tensorflow_str",
    "cv_dnn_readNetFromDarknet_VectorOfuchar_VectorOfuchar": "read_net_from_darknet_buffer",
    "cv_dnn_readNetFromDarknet_const_char_X_size_t_const_char_X_size_t": "read_net_from_darknet_str",
    "cv_dnn_Net_getMemoryConsumption_const_int_VectorOfVectorOfint_size_t_size_t": "get_memory_consumption_for_layer",
    "cv_dnn_Net_getMemoryConsumption_const_VectorOfVectorOfint_VectorOfint_VectorOfsize_t_VectorOfsize_t": "get_memory_consumption_for_layers",
}

# list of classes to skip, elements are regular expressions for re.match() against ClassInfo.fullname
class_ignore_list = (
    ### core ###
    "Cv[A-Z]",  # C style types
    "Ipl.*",
    "cv::Mutex", "cv::softfloat", "cv::softdouble", "cv::float16_t",  # have corresponding Rust implementation
    "cv::Exception",
    "cv::RNG.*",  # maybe
    "cv::SVD",
    "cv::MatAllocator",
    "cv::SparseMat",  # fixme
    "cv::TLSDataContainer",
    "cv::MatConstIterator",
    "cv::_InputArray", "cv::_OutputArray", "cv::_InputOutputArray",

    ### stitching ###
    "cv::CylindricalWarperGpu", "cv::PlaneWarperGpu", "cv::SphericalWarperGpu",

    ### videostab ###
    "cv::videostab::DensePyrLkOptFlowEstimatorGpu",
    "cv::videostab::KeypointBasedMotionEstimatorGpu",
    "cv::videostab::MoreAccurateMotionWobbleSuppressorGpu",
    "cv::videostab::SparsePyrLkOptFlowEstimatorGpu",

    ### ml ###
    "cv::ml::SimulatedAnnealingSolverSystem",  # only defined in docs

    ### dnn ###
    "cv::dnn::_Range",
)

# list of constants to skip, elements are regular expressions for re.match() against ConstInfo.name
const_ignore_list = (
    "CV_EXPORTS_W", "CV_MAKE_TYPE",
    "CV_IS_CONT_MAT", "CV_RNG_COEFF", "IPL_IMAGE_MAGIC_VAL",
    "CV_SET_ELEM_FREE_FLAG", "CV_FOURCC_DEFAULT",
    "CV_WHOLE_ARR", "CV_WHOLE_SEQ", "CV_PI", "CV_2PI", "CV_LOG2",
    "CV_TYPE_NAME_IMAGE",
    "CV_SUPPRESS_DEPRECATED_START",
    "CV_SUPPRESS_DEPRECATED_END",
    "__CV_BEGIN__", "__CV_END__", "__CV_EXIT__",
    "CV_IMPL_IPP", "CV_IMPL_MT", "CV_IMPL_OCL", "CV_IMPL_PLAIN",
    "CV_TRY", "CV_CATCH_ALL",
    "CV__DEBUG_NS_",
    "UINT64_1",
    "CV_STRUCT_INITIALIZER", "CV__ENABLE_C_API_CTORS",
    "VSX_IMPL_MULH_",
    "CV__DNN_EXPERIMENTAL_NS_",
    "CV_Sts",
    "CV_ALWAYS_INLINE",
)

# set of functions that should have unsafe in their declaration, element is FuncInfo.identifier
func_unsafe_list = {
    # allocates uninitialized memory
    "cv_Mat_Mat_int_int_int",
    "cv_Mat_Mat_Size_int",
    "cv_Mat_Mat_VectorOfint_int",
    "cv_Mat_set_data_uchar_X",
}

# dict of types to replace if cannot be handled automatically
# key: typeid (full class path with . replaces by ::)
# value: replacement typeid
type_replace = {
    "InputArray": "cv::Mat",
    "InputArrayOfArrays": "vector<cv::Mat>",
    "OutputArray": "cv::Mat",
    "OutputArrayOfArrays": "vector<cv::Mat>",
    "InputOutputArrayOfArrays": "vector<cv::Mat>",
    "InputOutputArray": "cv::Mat",
    "_InputArray": "cv::Mat",
    "_OutputArray": "cv::Mat",
    "_InputOutputArray": "cv::Mat",
    "vector_Mat": "vector<cv::Mat>",
    "vector_float": "vector<float>",
    "_Range": "cv::Range",
    "Point_<int>": "Point2i",
    "Point_<int64>": "Point2l",
    "Point_<float>": "Point2f",
    "Point_<double>": "Point2d",
    "Rect_<int>": "Rect2i",
    "Rect_<float>": "Rect2f",
    "Rect_<double>": "Rect2d",
    "Size_<int64>": "Size2l",
    "Size_<float>": "Size2f",
    "Size_<double>": "Size2d",
    "Scalar_<double>": "Scalar",
}

# dict for handling primitives
# key: primitive typeid
# value: dict
#   keys: "cpp_extern", "rust_local"
#   values: corresponding native typeid
# fixme, is "cpp_extern" needed at all?
primitives = {
    "void": {"cpp_extern": "void", "rust_local": "()"},

    "bool": {"cpp_extern": "bool", "rust_local": "bool"},

    "char": {"cpp_extern": "char", "rust_local": "i8"},
    "schar": {"cpp_extern": "char", "rust_local": "i8"},
    "signed char": {"cpp_extern": "char", "rust_local": "i8"},
    "uchar": {"cpp_extern": "unsigned char", "rust_local": "u8"},
    "unsigned char": {"cpp_extern": "unsigned char", "rust_local": "u8"},

    "short": {"cpp_extern": "short", "rust_local": "i16"},
    "signed short": {"cpp_extern": "short", "rust_local": "i16"},
    "ushort": {"cpp_extern": "unsigned short", "rust_local": "u16"},
    "unsigned short": {"cpp_extern": "unsigned short", "rust_local": "u16"},

    "int": {"cpp_extern": "int", "rust_local": "i32"},
    "signed int": {"cpp_extern": "int", "rust_local": "i32"},
    "uint": {"cpp_extern": "unsigned int", "rust_local": "u32"},
    "unsigned": {"cpp_extern": "unsigned int", "rust_local": "u32"},
    "unsigned int": {"cpp_extern": "unsigned int", "rust_local": "u32"},
    "uint32_t": {"cpp_extern": "uint32_t", "rust_local": "u32"},

    "size_t": {"cpp_extern": "std::size_t", "rust_local": "size_t"},

    "int64": {"cpp_extern": "int64", "rust_local": "i64"},
    "__int64": {"cpp_extern": "int64", "rust_local": "i64"},
    "signed __int64": {"cpp_extern": "int64", "rust_local": "i64"},
    "uint64": {"cpp_extern": "uint64", "rust_local": "u64"},
    "unsigned __int64": {"cpp_extern": "uint64", "rust_local": "u64"},
    "unsigned long long": {"cpp_extern": "unsigned long long", "rust_local": "u64"},
    "int64_t": {"cpp_extern": "int64_t", "rust_local": "i64"},
    "uint64_t": {"cpp_extern": "uint64_t", "rust_local": "u64"},

    "float": {"cpp_extern": "float", "rust_local": "f32"},
    "double": {"cpp_extern": "double", "rust_local": "f64"},
}

_forward_const_rust_safe = template("""
${doc_comment}${visibility}fn ${r_name}<T: core::DataType>(${args}) -> Result<&T> { ${pre_call_args}self._${r_name}(${forward_args}) }
            
""")
_forward_mut_rust_safe = template("""
${doc_comment}${visibility}fn ${r_name}<T: core::DataType>(${args}) -> Result<&mut T> { ${pre_call_args}self._${r_name}(${forward_args}) }

""")

# dict of functions with manual implementations
# key: FuncInfo.identifier
# value: dict
#   keys: "rust_safe", "rust_extern", "cpp", missing key means skip particular implementation
#   values: template to use for manual implementation or "~" to use default implementation
func_manual = {
    "cv_Mat_at_int": {
        "rust_safe": _forward_mut_rust_safe,
    },
    "cv_Mat_at_const_int": {
        "rust_safe": _forward_const_rust_safe,
    },
    "cv_Mat_at_int_int_int": {
        "rust_safe": _forward_mut_rust_safe,
    },
    "cv_Mat_at_const_int_int_int":  {
        "rust_safe": _forward_const_rust_safe,
    },
    "cv_Mat_at_int_int": {
        "rust_safe": _forward_mut_rust_safe,
    },
    "cv_Mat_at_const_int_int": {
        "rust_safe": _forward_const_rust_safe,
    },
}

# dict of manual declaration for types
# key: module name
# value: dict
#   key: local rust type name
#   value: dict
#     keys: "cpp", "rust", missing key means skip particular implementation
#     values: template to use for manual implementation or "~" to use default implementation
type_manual = {}


def _base_type_alias(module, rust_name, rust_definition, cpp_field_type, cpp_fields):
    if module not in type_manual:
        type_manual[module] = {}
    type_manual[module][rust_name] = {
        "rust": template(template("""
            ${doc_comment}pub type ${rust_local} = ${definition};
        """).substitute({"doc_comment": "${doc_comment}", "rust_local": "${rust_local}", "definition": rust_definition})),
        "cpp": "~",
    }
    cpp_props = [[cpp_field_type, x, "", "/RW"] for x in cpp_fields]
    if module not in decls_manual_pre:
        decls_manual_pre[module] = []
    decls_manual_pre[module].insert(0, ("class cv.{}".format(rust_name), "", ["/Simple"], cpp_props))


_base_type_alias("core", "Scalar", "core::Scalar_<f64>", "double", ("data[4]",))

for s in (2, 3, 4, 6, 8):
    types = ("b", "unsigned char"), \
            ("s", "short"), \
            ("w", "unsigned short"), \
            ("i", "int"), \
            ("l", "int64"), \
            ("f", "float"), \
            ("d", "double")
    if s == 6:
        types = (x for x in types if x[0] in ("d", "f", "i"))
    elif s == 8:
        types = (x for x in types if x[0] == "i")
    for t in types:
        rust_local = primitives[t[1]]["rust_local"]
        if s == 2:
            if t[0] == "i":
                _base_type_alias("core", "Rect", "core::Rect_<{}>".format(rust_local), t[1], ("x", "y", "width", "height"))
                _base_type_alias("core", "Point", "core::Point_<{}>".format(rust_local), t[1], ("x", "y"))
                _base_type_alias("core", "Size", "core::Size_<{}>".format(rust_local), t[1], ("width", "height"))
            if t[0] in ("i", "f", "d"):
                _base_type_alias("core", "Rect{}{}".format(s, t[0]), "core::Rect_<{}>".format(rust_local), t[1], ("x", "y", "width", "height"))
            if t[0] in ("i", "l", "f", "d"):
                _base_type_alias("core", "Point{}{}".format(s, t[0]), "core::Point_<{}>".format(rust_local), t[1], ("x", "y"))
                _base_type_alias("core", "Size{}{}".format(s, t[0]), "core::Size_<{}>".format(rust_local), t[1], ("width", "height"))
        if t[0] != "l":
            _base_type_alias("core", "Vec{}{}".format(s, t[0]), "core::Vec{}<{}>".format(s, rust_local), t[1], ("data[{}]".format(s),))

# set of types that must be generated as traits, elements are typeids
forced_class_trait = {
    "cv::Algorithm",
    "cv::BackgroundSubtractor",
    "cv::dnn::Layer",
}

# set of types that must not be treated as simple, most probably will be treated as boxed, elements are ClassInfo.fullname
force_class_not_simple = {
    "cv::dnn::Net",  # marked as Simple, but it's actually boxed
}

# dict of reserved Rust keywords and their replacement to be used in var, function and class names
# key: reserved keyword
# value: replacement
reserved_rename = {
    "type": "_type",
    "box": "_box",
    "ref": "_ref",
    "in": "_in",
    "use": "_use",
}

# list of modules that are imported into every other module so there is no need to reference them using full path, elements are module names
static_modules = ("core", "sys", "types")


def decl_patch(module, decl):
    if module == "objdetect":
        # replace Mat with explicit vector because detect functions only accept vector InputArray
        if decl[0] == "cv.QRCodeDetector.detect" or decl[0] == "cv.QRCodeDetector.detectAndDecode":
            pts_arg = decl[3][1]
            if pts_arg[0] == "OutputArray" and pts_arg[1] == "points":
                decl[3][1][0] = "std::vector<Point>&"
        elif decl[0] == "cv.QRCodeDetector.decode" or decl[0] == "cv.decodeQRCode":
            pts_arg = decl[3][1]
            if pts_arg[0] == "InputArray" and pts_arg[1] == "points":
                decl[3][1][0] = "const std::vector<Point>&"
    return decl


#
#       TEMPLATES
#

T_CPP_MODULE = template("""
//
// This file is auto-generated, please don't edit!
//

#include "stdint.h"
#include "common.h"

typedef int64_t int64;

#include <iostream>
#include "opencv2/opencv_modules.hpp"
#include <string>
#include "common_opencv.h"

using namespace cv;
#include "types.h"
$includes


extern "C" {

#include "return_types.h"

$code

} // extern "C"

""")

const_private_list = (
    "CV_MOP_.+",
    "CV_INTER_.+",
    "CV_THRESH_.+",
    "CV_INPAINT_.+",
    "CV_RETR_.+",
    "CV_CHAIN_APPROX_.+",
    "OPPONENTEXTRACTOR",
    "GRIDDETECTOR",
    "PYRAMIDDETECTOR",
    "DYNAMICDETECTOR",
)


#
#       Helpers
#

def camel_case_to_snake_case(name):
    res = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    res = re.sub('([a-z0-9])([A-Z])', r'\1_\2', res)
    res = re.sub(r'\B([23])_(D)\b', r'_\1\2', res)  # fix 2_d and 3_d
    return res.lower()


def bump_counter(name):
    """
    :type name: str
    :rtype: str
    """
    pos = len(name) - 1
    for pos in range(len(name) - 1, 0, -1):
        if not name[pos].isdigit():
            break
    base_name = name[:pos + 1]
    try:
        counter = int(name[pos + 1:])
    except ValueError:
        base_name += "_"
        counter = 0
    return "{}{}".format(base_name, counter + 1)


def split_known_namespace(name, namespaces):
    """
    :type name: str
    :type namespaces: iterable
    :rtype: (str, str)
    """
    if "::" in name:
        for namespace in sorted(namespaces, key=len, reverse=True):
            namespace_colon = namespace + "::"
            if name.startswith(namespace_colon):
                return namespace, name[len(namespace_colon):]
        return "", name
    else:
        return "", name

#
#       AST-LIKE
#


class GeneralInfo:
    def __init__(self, gen, name, namespaces):
        """
        :type gen: RustWrapperGenerator
        :type name: str
        :type namespaces: frozenset
        """
        self.gen = gen
        self.fullname, self.namespace, self.classpath, self.classname, self.name = self.do_parse_name(name, namespaces)
        logging.info(
            "parse_name: %s with %s -> fullname:%s namespace:%s classpath:%s classname:%s name:%s" %
            (name, namespaces, self.fullname, self.namespace, self.classpath, self.classname, self.name)
        )

    def do_parse_name(self, name, namespaces):
        """
        input: full name and available namespaces
        returns: (fullname, namespace, classpath, classname, name)
            fullname clean of prefix like "const, class, ..."
        """
        name = name \
            .replace("const ", "") \
            .replace("struct ", "") \
            .replace("class ", "") \
            .replace("typedef ", "") \
            .replace("callback ", "") \
            .replace(".", "::")
        space_name, local_name = split_known_namespace(name, namespaces)
        pieces = local_name.split("::")
        if len(pieces) > 2:  # <class>.<class>.<class>.<name>
            return name, space_name, "::".join(pieces[:-1]), pieces[-2], pieces[-1]
        elif len(pieces) == 2:  # <class>.<name>
            return name, space_name, pieces[0], pieces[0], pieces[1]
        elif len(pieces) == 1:  # <name>
            return name, space_name, "", "", pieces[0]
        else:
            return name, space_name, "", ""  # error?!


class ArgInfo:
    def __init__(self, gen, arg_tuple):  # [ ctype, name, def val, [mod], argno ]
        """
        :type gen: RustWrapperGenerator
        :param arg_tuple:
        """
        self.gen = gen
        typ = arg_tuple[0]
        self.type = self.gen.get_type_info(typ)
        self.name = arg_tuple[1]
        if not self.name:
            self.name = "unnamed_arg"
        self.rsname = camel_case_to_snake_case(reserved_rename.get(self.name, self.name))
        self.defval = ""
        if len(arg_tuple) > 2:
            self.defval = arg_tuple[2]
        self.out = ""
        if typ in ("OutputArray", "OutputArrayOfArrays") or len(arg_tuple) > 3 and "/O" in arg_tuple[3] or self.type.is_by_ref and not self.type.is_const:
            self.out = "O"
        if typ in ("InputOutputArray", "InputOutputArrayOfArrays") or len(arg_tuple) > 3 and "/IO" in arg_tuple[3]:
            self.out = "IO"

    def is_output(self):
        return self.out in ("O", "IO")

    def __repr__(self):
        return template("ARG $ctype$p $name=$defval").substitute(ctype=self.type,
                                                                  p=" *" if isinstance(self.type, RawPtrTypeInfo) else "",
                                                                  name=self.name,
                                                                  defval="" #self.defval
                                                                )


class FuncInfo(GeneralInfo):
    KIND_FUNCTION    = "(function)"
    KIND_METHOD      = "(method)"
    KIND_CONSTRUCTOR = "(constructor)"

    TEMPLATES = {
        "cpp": template("""
                // parsed: ${fullname}
                // as:     ${repr}
                ${args}// Return value: ${rv_type}
                ${return_wrapper_type} ${identifier}(${decl_cpp_args}) {
                    try {${pre_call_args}
                ${call}${post_call_args}
                ${rv}
                    } CVRS_CATCH(${return_wrapper_type})
                }

            """),

        "cpp_doc_arg": template("""// Arg ${repr}${ptr} ${type} = ${defval}${ignored}\n"""),

        "rust_safe": template("""
                ${doc_comment}${visibility}${unsafety_decl}fn ${r_name}${generic_decl}(${args}) -> Result<$rv_rust_full> {${pre_call_args}
                    ${prefix}${unsafety_call}{ sys::${identifier}(${call_args}) }.into_result()${suffix}${rv}${post_call_args}
                }
                
            """),

        "rust_safe_rv_string": template("""
                .map(crate::templ::receive_string)"""),

        "rust_safe_rv_string_mut": template("""
                .map(crate::templ::receive_string_mut)"""),

        "rust_safe_rv_const_raw_ptr": template("""
            .and_then(|x| unsafe { x.as_ref() }.ok_or_else(|| Error::new(core::StsNullPtr, format!("Function returned Null pointer"))))"""),

        "rust_safe_rv_mut_raw_ptr": template("""
            .and_then(|x| unsafe { x.as_mut() }.ok_or_else(|| Error::new(core::StsNullPtr, format!("Function returned Null pointer"))))"""),

        "rust_safe_rv_vector_box_ptr": template(""".map(|x| ${rv_rust_full} { ptr: x })"""),

        "rust_safe_rv_other": template(""""""),

        "rust_extern": template("""
            pub fn ${identifier}(${args}) -> ${return_wrapper_type};
         """),
    }

    def __init__(self, gen, module, decl, namespaces=frozenset()):  # [ funcname, return_ctype, [modifiers], [args] ]
        """
        :type gen: RustWrapperGenerator
        :type module: str
        :type decl: list
        :type namespaces: frozenset
        """
        GeneralInfo.__init__(self, gen, decl[0], namespaces)
        self.module = module

        self.is_ignored = False
        if self.classname and not self.classname.startswith("operator"):
            self.ci = gen.get_class(self.classname)
            if not self.ci:
                if self.classname == "std" or "<" in self.classname:
                    self.is_ignored = True
                else:
                    raise NameError("class not found: " + self.classname)
            if "/A" in decl[2]:
                self.ci.is_trait = True
            if self.classname == self.name:
                self.kind = self.KIND_CONSTRUCTOR
                self.name = "new"
                self.type = gen.get_type_info(self.classname)
            else:
                self.kind = self.KIND_METHOD
                self.type = gen.get_type_info(decl[1])
        else:
            self.kind = self.KIND_FUNCTION
            self.ci = None  # type: ClassInfo
            self.type = gen.get_type_info(decl[1])

        self.identifier = self.fullname.replace("::", "_")

        self.is_ignored = self.is_ignored or "/H" in decl[2] or "/I" in decl[2]

        self.is_const = "/C" in decl[2]
        self.is_static = "/S" in decl[2]
        self.attr_accessor_type = None
        if "/ATTRGETTER" in decl[2]:
            self.attr_accessor_type = "r"
        elif "/ATTRSETTER" in decl[2]:
            self.attr_accessor_type = "w"
        self.has_callback_arg = False
        has_userdata_arg = False

        if self.is_const:
            self.identifier += "_const"

        self.args = []
        for arg in decl[3]:
            ai = ArgInfo(gen, arg)
            if self.has_callback_arg and ai.name == "userdata":
                has_userdata_arg = True
            while any(True for x in self.args if x.name == ai.name):
                ai.name = bump_counter(ai.name)
                ai.rsname = camel_case_to_snake_case(reserved_rename.get(ai.name, ai.name))
            self.args.append(ai)
            self.identifier += "_" + ai.type.rust_safe_id
            if isinstance(ai.type, CallbackTypeInfo):
                self.has_callback_arg = True

        if self.has_callback_arg and not has_userdata_arg:
            logging.info("ignore function with callback, but without userdata %s %s in %s"%(self.kind, self.name, self.ci))
            self.is_ignored = True

        if len(decl) > 5:
            self.comment = decl[5]
        else:
            self.comment = ""

        self.cname = self.cppname = self.name
        self.is_safe = self.identifier not in func_unsafe_list

        if self.name.startswith("~"):
            logging.info("ignore destructor %s %s in %s"%(self.kind, self.name, self.ci))
            self.is_ignored = True

        if self.name.startswith("operator") or self.fullname.startswith("operator "):
            logging.info("ignore %s %s in %s"%(self.kind, self.name, self.ci))
            self.is_ignored = True

    def _get_manual_implementation_tpl(self, section):
        params = func_manual.get(self.identifier)
        if params is not None:
            tmpl = params.get(section)
            if tmpl is None:
                return template("")
            elif tmpl == "~":
                return None
            return tmpl
        return None

    def is_constructor(self):
        return self.kind == self.KIND_CONSTRUCTOR

    def is_instance_method(self):
        return not self.is_static and self.ci and not self.is_constructor()

    def rv_type(self):
        """
        :rtype: TypeInfo
        """
        if self.is_constructor():
            if self.ci:
                return self.gen.get_type_info(self.ci.fullname)
            else:
                return None
        else:
            return self.type

    def reason_to_skip(self):
        if self.identifier in self.gen.generated:
            return "already there"

        if func_rename.get(self.identifier) == "-":
            return "ignored by rename table"

        if self.identifier in func_manual:
            return None

        if self.name.startswith("operator"):
            return "can not map %s yet"%(self.name)

        if not self.rv_type():
            return "rv_header_type returns None. this is an error. (class not found ?)"

        if self.type.is_ignored:
            return "return type class %s is ignored"%(self.type)

        if self.rv_type().is_ignored:
            return "return value type is ignored"

        if self.kind == self.KIND_CONSTRUCTOR and self.ci.is_trait:
            return "skip constructor of abstract class"

        for a in self.args:
            if a.type.is_ignored:
                return "can not map type %s yet"%(a.type)

        return None

    def r_name(self):
        name = func_rename.get(self.identifier)
        if name is None:
            name = "new" if self.is_constructor() else self.name
        else:
            if "+" in name:
                name = name.replace("+", self.name)
                name = camel_case_to_snake_case(reserved_rename.get(name, name))
            return name
        return camel_case_to_snake_case(reserved_rename.get(name, name))

    def gen_cpp(self):
        decl_cpp_args = []
        pre_call_args = []
        post_call_args = []
        args = ""
        if self.is_instance_method():
            # fixme? add RawPtr handling
            decl_cpp_args.append(self.ci.type_info().cpp_extern + " instance")

        call_cpp_args = []
        for arg in self.args:
            ignored = ptr = ""
            if arg.type.is_ignored:
                ignored = " (ignored)"
            if isinstance(arg.type, RawPtrTypeInfo):
                ptr = " (ptr)"
            pre_call_arg = arg.type.cpp_arg_pre_call(arg.rsname)
            if pre_call_arg:
                pre_call_args.append(pre_call_arg)
            post_call_arg = arg.type.cpp_arg_post_call(arg.rsname)
            if post_call_arg:
                post_call_args.append(post_call_arg)

            args += FuncInfo.TEMPLATES["cpp_doc_arg"].substitute(combine_dicts(arg.__dict__, {
                "repr": repr(arg),
                "ptr": ptr,
                "ignored": ignored
            }))

            decl_cpp_args.append(arg.type.cpp_arg_func_decl(arg.name, arg.is_output()))
            call_cpp_args.append(arg.type.cpp_arg_func_call(arg.name, arg.is_output()))

        # cpp method call with prefix
        if self.is_constructor():
            call_name = self.ci.fullname
        elif self.ci is None or self.is_static:
            if self.namespace == "":
                call_name = self.cppname
            else:
                call_name = self.fullname
        else:
            call_name = self.ci.type_info().cpp_method_call_name(self.cppname)

        # actual call
        call = self.rv_type().cpp_method_call_invoke(call_name, ", ".join(call_cpp_args), self.is_constructor(), self.attr_accessor_type)

        template_vars = combine_dicts(self.__dict__, {
            "repr": repr(self),
            "rv_type": self.rv_type(),
            "args": args,
            "return_wrapper_type": self.rv_type().rust_cpp_return_wrapper_type(),
            "decl_cpp_args": ", ".join(decl_cpp_args),
            "pre_call_args": "".join("\n" + indent(x, 2) + ";" for x in pre_call_args),
            "post_call_args": "".join("\n" + indent(x, 2) + ";" for x in post_call_args),
            "call": indent(call, 2),
            "rv": indent(self.rv_type().cpp_method_return(self.is_constructor()), 2),
        })

        tmpl = self._get_manual_implementation_tpl("cpp")
        if tmpl is None:
            self.rv_type().gen_return_wrappers(self.gen.cpp_dir, self.gen.rust_dir)
            tmpl = FuncInfo.TEMPLATES["cpp"]
        return tmpl.substitute(template_vars)

    def gen_rust_extern(self):
        args = []
        if self.is_instance_method():
            args.append(self.ci.type_info().rust_extern_self_func_decl(not self.is_const))
        for a in self.args:
            args.append(a.type.rust_extern_arg_func_decl(a.rsname))
        template_vars = combine_dicts(self.__dict__, {
            "args": ", ".join(args),
            "return_wrapper_type": self.rv_type().rust_cpp_return_wrapper_type(),
        })
        tmpl = self._get_manual_implementation_tpl("rust_extern") or FuncInfo.TEMPLATES["rust_extern"]
        return tmpl.substitute(template_vars)

    def gen_safe_rust(self):
        args = []
        call_args = []
        forward_args = []
        pre_call_args = []
        post_call_args = []

        lifetimes = set()  # todo implement lifetime elision rules, type should specify only &type and do replacement of & with &'a
        # if self.rv_type().rust_lifetimes:
        #     lifetimes.add(self.rv_type().rust_lifetimes)

        # for a in self.args:
        #     if a.type.rust_lifetimes:
        #         lifetimes.add(a.type.rust_lifetimes)

        if len(lifetimes) > 0:
            lifetimes = ", ".join(lifetimes)
        else:
            lifetimes = ""

        if self.is_instance_method():
            args.append(self.ci.type_info().rust_self_func_decl(not self.is_const))
            call_args.append(self.ci.type_info().rust_self_func_call(not self.is_const))

        generic_decls = []

        # todo: convert some *const Mat to slices in rust
        for arg in self.args:
            call_args.append(arg.type.rust_arg_func_call(arg.rsname, arg.is_output()))
            forward_args.append(arg.type.rust_arg_forward(arg.rsname))
            pre_call_arg = arg.type.rust_arg_pre_call(arg.rsname)
            if pre_call_arg:
                pre_call_args.append(pre_call_arg)
            post_call_arg = arg.type.rust_arg_post_call(arg.rsname)
            if post_call_arg:
                post_call_args.append(post_call_arg)
            gdecl = arg.type.rust_generic_decl()
            if gdecl:
                generic_decls.append(gdecl)
            if self.has_callback_arg and arg.name == "userdata":
                continue
            args.append(arg.type.rust_arg_func_decl(arg.rsname, arg.is_output()))

        pub = "" if self.ci and self.ci.type_info().is_trait and not self.is_static else "pub "

        doc_comment = self.gen.reformat_doc(self.comment, self)

        defattr_doc_comment = ""
        for arg in (x for x in self.args if x.defval != ""):
            if not defattr_doc_comment:
                defattr_doc_comment += "///\n/// ## C++ default parameters\n"
            defattr_doc_comment += "/// * %s: %s\n" % (arg.rsname, arg.defval)
        if defattr_doc_comment:
            attr_pos = doc_comment.find("#[")
            if attr_pos == -1:
                attr_pos = len(doc_comment)
            doc_comment = doc_comment[:attr_pos] + defattr_doc_comment + doc_comment[attr_pos:]
        prefix = ""
        suffix = ""
        if len(post_call_args) > 0:
            post_call_args.append("return out")
            prefix = "let out = "
            suffix = ";"

        template_vars = combine_dicts(self.__dict__, {
            "doc_comment": doc_comment,
            "rv_rust_full": self.rv_type().rust_full,
            "unsafety_decl": "" if self.is_safe else "unsafe ",
            "unsafety_call": "unsafe " if self.is_safe else "",
            "visibility": pub,
            "generic_decl": "<{}>".format(", ".join(generic_decls)) if len(generic_decls) >= 1 else "",
            "prefix": prefix,
            "suffix": suffix,
            "args": ", ".join(args),
            "pre_call_args": "".join("\n" + indent(x) + ";" for x in pre_call_args),
            "post_call_args": "".join("\n" + indent(x) + ";" for x in post_call_args),
            "r_name": self.r_name(),
            "call_args": ", ".join(call_args),
            "forward_args": ", ".join(forward_args),
        })
        if isinstance(self.rv_type(), StringTypeInfo) or isinstance(self.rv_type(), RawPtrTypeInfo) and self.rv_type().is_string():
            if self.rv_type().is_const:
                rv_rust = FuncInfo.TEMPLATES["rust_safe_rv_string"].substitute(template_vars)
            else:
                rv_rust = FuncInfo.TEMPLATES["rust_safe_rv_string_mut"].substitute(template_vars)
        elif isinstance(self.rv_type(), RawPtrTypeInfo):
                rv_rust = FuncInfo.TEMPLATES["rust_safe_rv_const_raw_ptr" if self.rv_type().is_const else "rust_safe_rv_mut_raw_ptr"].substitute(template_vars)
        elif self.rv_type().is_by_ptr:
            rv_rust = FuncInfo.TEMPLATES["rust_safe_rv_vector_box_ptr"].substitute(template_vars)
        else:
            rv_rust = FuncInfo.TEMPLATES["rust_safe_rv_other"].substitute(template_vars)

        template_vars["rv"] = rv_rust

        block = self._get_manual_implementation_tpl("rust_safe") or FuncInfo.TEMPLATES["rust_safe"]
        block = block.substitute(template_vars)

        if self.kind == self.KIND_FUNCTION:
            return block
        else:
            return indent(block)

    def __repr__(self):
        if self.kind == self.KIND_FUNCTION:
            return "%s %s"%(self.fullname, self.kind)
        else:
            return "%s %s %s . %s"%(self.fullname, self.kind, self.ci, self.name)


class ClassPropInfo:
    def __init__(self, decl):  # [f_ctype, f_name, '', '/RW']
        self.is_const = "/C" in decl[3]
        self.ctype = "{}{}".format("const " if self.is_const else "", decl[0])
        self.name = decl[1]
        self.comment = decl[2]
        self.rw = "/RW" in decl[3]

    def __repr__(self):
        return template("PROP $ctype $name").substitute(ctype=self.ctype, name=self.name)


class ClassInfo(GeneralInfo):
    def __init__(self, gen, module, decl, namespaces):  # [ 'class/struct cname', ': base', [modlist] ]
        """
        :type gen: RustWrapperGenerator
        :type module: str
        :type decl: list
        :type namespaces: frozenset
        """
        GeneralInfo.__init__(self, gen, decl[0], namespaces)
        self.methods = []  # type: list[FuncInfo]
        self.namespaces = namespaces
        self.module = module
        self.is_simple = self.is_ignored = self.is_ghost = self.is_callback = False
        self.is_trait = self.fullname in forced_class_trait
        self.classname = self.name
        self.comment = ""
        if len(decl) > 5:
            self.comment = decl[5]
        for m in decl[2]:
            if (m == "/Simple" or m == "/Map") and self.fullname not in force_class_not_simple:
                self.is_simple = True
            if m == "/Hidden":
                self.is_ignored = True
            if m == "/Ghost":
                self.is_ghost = True
            if m == "/Callback":
                self.is_callback = True
        if self.classpath:
            ci = self.gen.get_class(self.classpath)
            if ci is not None and ci.is_ignored:
                self.is_ignored = True

        self.nested_cname = self.fullname.replace("::", "_")

        bases = decl[1][1:].strip()
        if len(bases):
            self.bases = [x for x in set(x.strip() for x in bases.split(",")) if x != self.fullname]
        else:
            self.bases = []

        for base in self.bases:
            typ = self.gen.get_class(base)
            if typ:
                typ.is_trait = True

        # class props
        self.props = []
        for p in decl[3]:
            self.props.append(ClassPropInfo(p))

        self.is_ignored = self.is_ignored or self.gen.class_is_ignored(self.fullname)

    def __repr__(self):
        attrs = []
        if self.is_simple:
            attrs.append("simple")
        if self.is_ignored:
            attrs.append("ignored")
        if self.is_ghost:
            attrs.append("ghost")
        if self.is_trait:
            attrs.append("trait")
        if len(attrs) == 0:
            return self.fullname
        else:
            return "{} ({})".format(self.fullname, ", ".join(attrs))

    def add_method(self, fi):
        logging.info("register %s %s in %s (%s)"%(fi.kind, fi.name, fi.ci, fi.identifier))
        self.methods.append(fi)

    def type_info(self):
        """
        :rtype: TypeInfo
        """
        return self.gen.get_type_info(self.fullname)

    def get_manual_declaration_tpl(self, section):
        if self.module in type_manual:
            module_types = type_manual[self.module]
            params = module_types.get(self.name)
            if params is not None:
                tmpl = params.get(section)
                if tmpl is None:
                    return template("")
                elif tmpl == "~":
                    return None
                return tmpl
        return None


class ConstInfo(GeneralInfo):
    TEMPLATES = {
        "rust_string": template("${doccomment}pub const ${name}: &'static str = ${value};\n"),
        "rust_int": template("${doccomment}pub const ${name}: i32 = ${value};\n"),
        "rust_usize": template("${doccomment}pub const ${name}: usize = ${value};\n"),
        "cpp_string": template("""    printf("pub static ${name}: &'static str = \\"%s\\";\\n", ${full_name});\n"""),
        "cpp_double": template("""    printf("pub const ${name}: f64 = %f;\\n", ${full_name});\n"""),
        "cpp_int": template("""    printf("pub const ${name}: i32 = 0x%x; // %i\\n", ${full_name}, ${full_name});\n"""),
    }

    def __init__(self, gen, decl, namespaces):
        """
        :type gen: RustWrapperGenerator
        :type decl: list
        :type namespaces: frozenset
        """
        GeneralInfo.__init__(self, gen, decl[0], namespaces)
        _, self.rustname = split_known_namespace(self.fullname, namespaces)
        self.rustname = self.rustname.replace("::", "_")
        self.cname = self.name.replace(".", "::")
        self.value = decl[1]

    def __repr__(self):
        return template("CONST $name=$value").substitute(name=self.name, value=self.value)

    def is_ignored(self):
        for c in const_ignore_list:
            if re.match(c, self.name):
                return True
        return False

    def gen_rust(self):
        name = self.rustname
        value = self.value
        while True:
            doccomment = ""
            m = re.match(r"^(.+?)\s*(?://\s*(.+)|/\*+\s*(.+?)\s*\*+/)$", value)  # xxx // comment OR xxx /** comment **/
            if m:
                value = m.group(1)
                doccomment = "/// {}\n".format(m.group(3) if m.group(2) is None else m.group(2))
            if value.startswith('"'):
                return ConstInfo.TEMPLATES["rust_string"].substitute(doccomment=doccomment, name=name, value=value)
            elif name in ("Mat_AUTO_STEP", ""):
                return ConstInfo.TEMPLATES["rust_usize"].substitute(doccomment=doccomment, name=name, value=value)
            elif re.match(r"^(-?[0-9]+|0x[0-9A-Fa-f]+)$", value):  # decimal or hexadecimal
                return ConstInfo.TEMPLATES["rust_int"].substitute(doccomment=doccomment, name=name, value=value)
            elif re.match(r"^\(?\s*(\d+\s*<<\s*\d+)\s*\)?$", value):  # (1 << 24)
                return ConstInfo.TEMPLATES["rust_int"].substitute(doccomment=doccomment, name=name, value=value)
            elif re.match(r"^\s*(\d+\s*\+\s*\d+)\s*$", value):  # 0 + 3
                return ConstInfo.TEMPLATES["rust_int"].substitute(doccomment=doccomment, name=name, value=value)
            ref_const = self.gen.get_const(value)
            if ref_const is not None:
                value = ref_const.value
                continue
            return None

    def gen_cpp_for_complex(self):
        # only use C-constant dumping for unnested const
        if len(self.fullname.split(".")) > 2:
            return ""
        elif self.fullname == "CV_VERSION":
            return ConstInfo.TEMPLATES["cpp_string"].substitute(name=self.rustname, full_name=self.fullname)
        elif self.fullname in ("MLN10", "RELATIVE_ERROR_FACTOR"):
            return ConstInfo.TEMPLATES["cpp_double"].substitute(name=self.rustname, full_name=self.fullname)
        else:
            return ConstInfo.TEMPLATES["cpp_int"].substitute(name=self.rustname, full_name=self.fullname)


class TypedefInfo(GeneralInfo):
    def __init__(self, gen, decl, namespaces):
        """
        :type gen: RustWrapperGenerator
        :type decl: list
        :type namespaces: frozenset
        """
        GeneralInfo.__init__(self, gen, decl[0], namespaces)
        self.alias = decl[1]
        self.comment = ""
        if len(decl) > 5:
            self.comment = decl[5]

    def typ(self):
        return self.gen.get_type_info(self.name)

    def alias_typ(self):
        return self.gen.get_type_info(self.alias)


class CallbackInfo(GeneralInfo):
    TEMPLATES = {
        "rust": template("""
        ${doc_comment}pub type ${name} = dyn FnMut(${args}) + Send + Sync + 'static;
        #[doc(hidden)] pub type ${name}Extern = Option<extern "C" fn(${extern_args})>;
        
        """),
    }

    def __init__(self, gen, decl, namespaces):
        """
        :type gen: RustWrapperGenerator
        :type decl: list
        :type namespaces: frozenset
        """
        GeneralInfo.__init__(self, gen, decl[0], namespaces)
        self.args = []
        self.is_ignored = False
        for arg in decl[3]:
            ai = ArgInfo(gen, arg)
            while any(True for x in self.args if x.name == ai.name):
                ai.name = bump_counter(ai.name)
                ai.rsname = camel_case_to_snake_case(reserved_rename.get(ai.name, ai.name))
            if ai.type.is_ignored:
                self.is_ignored = True
            self.args.append(ai)

        if len(decl) > 5:
            self.comment = decl[5]
        else:
            self.comment = ""

    def gen_rust(self):
        args = []
        extern_args = []
        for arg in self.args:
            if arg.type.is_ignored:
                return None
            extern_args.append(arg.type.rust_extern_arg_func_decl(arg.rsname, arg.is_output()))
            if arg.name != "userdata":
                args.append(arg.type.rust_full)
        return CallbackInfo.TEMPLATES["rust"].substitute(combine_dicts(self.__dict__, {
            "doc_comment": self.gen.reformat_doc(self.comment),
            "args": ", ".join(args),
            "extern_args": ", ".join(extern_args),
        }))


class TypeInfo(object):
    def __init__(self, gen, typeid):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        """
        self.is_by_ref = typeid.endswith("&")
        if self.is_by_ref:
            typeid = typeid[:-1].strip()
        self.is_const = typeid.startswith("const ")  # type has C++ const modifier
        self.typeid = typeid.replace("const ", "").strip()  # e.g. "vector<cv::Mat>", "std::vector<int>", "float"
        self.gen = gen
        self.is_ignored = False  # don't generate
        # False: types that contain ptr field to actual heap allocated data (e.g. BoxedClass, Vector, SmartPtr)
        # True: types that are getting passed by value (e.g. Primitive, SimpleClass)
        self.is_by_ptr = False
        self.is_trait = False  # don't generate struct, generate trait (abstract classes and classes inside forced_trait_classes)
        self.is_copy = False  # true for types that are Copy in Rust (e.g. Primitive, SimpleClass)

        self.cpp_extern = ""  # cpp type used on the boundary between Rust and C (e.g. in return wrappers)
        self.cpptype = self.typeid
        self.c_safe_id = "XX"  # c safe type identifier used for file names and return wrappers

        _, self.rust_local = split_known_namespace(self.typeid, gen.namespaces)
        self.rust_local = self.rust_local.replace("::", "_")  # only the type name for Rust without module path
        self.rust_safe_id = self.rust_local  # rust safe type identifier used for file and function names
        self.rust_full = ""  # full module path (with modules/crate::) to Rust type
        self.rust_extern = ""  # Rust type used on the boundary between Rust and C (e.g. in return wrappers)
        # self.rust_lifetimes = ""  # for reference types it's the definition of lifetimes that need to be present in function

        self.inner = None  # type: TypeInfo  # inner type for container types

        self.base_templates = {
            "cpp_void": template("""
                // $typeid
                struct ${return_wrapper_type} {
                    int error_code;
                    char* error_msg;
                };
            """),

            "cpp_non_void": template("""
                // $typeid
                struct ${return_wrapper_type} {
                    int error_code;
                    char* error_msg;
                    ${cpp_extern} result;
                };
            """),

            "rust_void": template("""
                // $typeid
                pub type ${return_wrapper_type} = cv_return_value<crate::types::Unit, ${rust_extern}>;
                
            """),

            "rust_non_void": template("""
                // $typeid
                pub type ${return_wrapper_type} = cv_return_value<${rust_extern}>;
                
            """),
        }

    def gen_wrappers(self):
        pass

    def gen_return_wrappers(self, cpp_dir, rust_dir):
        """
        :type cpp_dir: str
        :type rust_dir: str
        """
        template_vars = combine_dicts(self.__dict__, {
            "return_wrapper_type": self.rust_cpp_return_wrapper_type(),
        })
        write_exc(
            "{}/{}.type.h".format(cpp_dir, template_vars["return_wrapper_type"]),
            lambda f: f.write(self.base_templates["cpp_void" if self.cpp_extern == "void" else "cpp_non_void"].substitute(template_vars))
        )
        write_exc(
            "{}/{}.rv.rs".format(rust_dir, template_vars["return_wrapper_type"]),
            lambda f: f.write(self.base_templates["rust_void" if self.cpp_extern == "void" else "rust_non_void"].substitute(template_vars))
        )

    def rust_generic_decl(self):
        return ""

    def rust_self_func_decl(self, is_output=False):
        """
        :type is_output: bool
        :rtype: str
        """
        if self.is_by_ptr:
            if is_output:
                return "&mut self"
            return "&self"
        return "self"

    def rust_arg_func_decl(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        if self.is_by_ptr:
            if is_output:
                return "{}: &mut {}".format(var_name, self.rust_full)
            return "{}: &{}".format(var_name, self.rust_full)
        if self.is_by_ref and not self.is_const:
            return "{}: &mut {}".format(var_name, self.rust_full)
        return "{}: {}".format(var_name, self.rust_full)

    def rust_arg_pre_call(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        return ""

    def rust_self_func_call(self, is_output=False):
        """
        :type is_output: bool
        :rtype: str
        """
        return self.rust_arg_func_call("self", is_output)

    def rust_arg_func_call(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        if self.is_by_ptr:
            # if isinstance(a.type, RawPtrTypeInfo):
            #     typ = a.type.inner
            # else:
            #     typ = a.type
            return "{}.as_raw_{}()".format(var_name, self.rust_local)
        return var_name

    def rust_arg_forward(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        return var_name

    def rust_extern_self_func_decl(self, is_output=False):
        """
        :type is_output: bool
        :rtype: str
        """
        if self.is_by_ptr:
            return "instance: *{} c_void".format("mut" if is_output else "const")
        return "instance: {}".format(self.rust_full)

    def rust_extern_arg_func_decl(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        if not self.is_by_ptr and self.is_by_ref and not self.is_const:
            return "{}: &mut {}".format(var_name, self.rust_extern)
        return "{}: {}".format(var_name, self.rust_extern)

    def rust_arg_post_call(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        return ""

    def rust_cpp_return_wrapper_type(self):
        """
        :rtype: str
        """
        return "cv_return_value_{}".format(self.c_safe_id)

    def cpp_arg_func_decl(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        if not self.is_by_ptr:
            if self.is_by_ref:
                if not self.is_const:
                    return "{}& {}".format(self.cpp_extern, var_name)
            elif is_output:
                return "{}* {}".format(self.cpp_extern, var_name)
        return "{} {}".format(self.cpp_extern, var_name)

    def cpp_arg_pre_call(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        return ""

    def cpp_arg_func_call(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        if self.is_by_ptr:
            return "*reinterpret_cast<{}*>({})".format(self.cpptype, var_name)
        return "*reinterpret_cast<{}*>(&{})".format(self.cpptype, var_name)

    def cpp_arg_post_call(self, var_name, is_output=False):
        """
        :type var_name: str
        :type is_output: bool
        :rtype: str
        """
        return ""

    def cpp_method_call_name(self, method_name):
        """
        :type method_name: str
        :rtype: str
        """
        return "reinterpret_cast<{}*>(&instance)->{}".format(self.cpptype, method_name)

    def cpp_method_call_invoke(self, call_name, call_args, is_constructor, attr_type):
        """
        :type call_name: str
        :type call_args: str
        :type is_constructor: bool
        :type attr_type: str|None
        :rtype: str
        """
        if is_constructor:
            if call_args == "":
                return "{} ret;".format(self.cpptype)
            return "{} ret({});".format(self.cpptype, call_args)
        if attr_type == "r":
            return "{} ret = {};".format(self.cpptype, call_name)
        elif attr_type == "w":
            return "{} = {};".format(call_name.replace("set_", ""), call_args)
        return "{} ret = {}({});".format(self.cpptype, call_name, call_args)

    def cpp_method_return(self, is_constructor):
        if self.is_by_ptr:
            if is_constructor:
                return "return { Error::Code::StsOk, NULL, ret };"
            else:
                return "return {{ Error::Code::StsOk, NULL, new {}(ret) }};".format(self.cpptype)
        return "return {{ Error::Code::StsOk, NULL, ret }};".format(self.cpp_extern)


class StringTypeInfo(TypeInfo):
    def __init__(self, gen, typeid):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        """
        super(StringTypeInfo, self).__init__(gen, typeid)
        self.cpp_extern = "const char*"
        self.cpptype = "String"
        self.rust_full = "String"
        if self.is_const:
            self.c_safe_id = "const_char_X"
            self.rust_extern = "*const c_char"
        else:
            self.c_safe_id = "char_X"
            self.rust_extern = "*mut c_char"

    def is_output(self):
        return self.is_by_ref and not self.is_const

    def rust_arg_func_decl(self, var_name, is_output=False):
        if self.is_output():
            return "{}: &mut String".format(var_name)
        return "{}: &str".format(var_name)

    def rust_arg_pre_call(self, var_name, is_output=False):
        if self.is_output():
            return "string_arg_output_send!(via {}_via)".format(var_name)
        return "string_arg!({}{})".format("" if self.is_const else "mut ", var_name)

    def rust_arg_func_call(self, var_name, is_output=False):
        if self.is_output():
            return "&mut {}_via".format(var_name)
        if self.is_const:
            return "{}.as_ptr()".format(var_name)
        return "{}.as_ptr() as _".format(var_name)  # fixme: use as_mut_ptr() when it's stabilized

    def rust_extern_arg_func_decl(self, var_name, is_output=False):
        if self.is_output():
            return "{}: *mut {}".format(var_name, self.rust_extern)
        return super(StringTypeInfo, self).rust_extern_arg_func_decl(var_name, is_output)

    def rust_arg_post_call(self, var_name, is_output=False):
        if self.is_output():
            return "string_arg_output_receive!({}_via => {})".format(var_name, var_name)
        return super(StringTypeInfo, self).rust_arg_post_call(var_name, is_output)

    def cpp_arg_func_decl(self, var_name, is_output=False):
        if self.is_output():
            return "{}* {}".format(self.cpp_extern, var_name)
        return super(StringTypeInfo, self).cpp_arg_func_decl(var_name, is_output)

    def cpp_arg_pre_call(self, var_name, is_output=False):
        if self.is_output():
            return "std::string {}_out".format(var_name)
        return super(StringTypeInfo, self).cpp_arg_pre_call(var_name, is_output)

    def cpp_arg_func_call(self, var_name, is_output=False):
        if self.is_output():
            return "{}_out".format(var_name)
        return "{}({})".format(self.cpptype, var_name)

    def cpp_arg_post_call(self, var_name, is_output=False):
        if self.is_output():
            return "*{} = strdup({}_out.c_str())".format(var_name, var_name)
        return super(StringTypeInfo, self).cpp_arg_post_call(var_name, is_output)

    def cpp_method_return(self, is_constructor):
        return "return { Error::Code::StsOk, NULL, strdup(ret.c_str()) };"

    def __str__(self):
        return "string"


class IgnoredTypeInfo(TypeInfo):
    def __init__(self, gen, typeid):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        """
        super(IgnoredTypeInfo, self).__init__(gen, typeid)
        self.is_ignored = True

    def __str__(self):
        return "Ignored(%s)"%(self.typeid)


class PrimitiveTypeInfo(TypeInfo):
    def __init__(self, gen, typeid):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        """
        super(PrimitiveTypeInfo, self).__init__(gen, typeid)
        primitive = primitives[self.typeid]
        self.cpp_extern = primitive["cpp_extern"]
        self.rust_extern = self.rust_full = self.rust_local = primitive["rust_local"]
        self.rust_safe_id = self.typeid.replace(" ", "_")
        self.c_safe_id = self.cpp_extern.replace(" ", "_").replace("*", "X").replace("::", "_")
        self.is_copy = True

    def cpp_arg_func_call(self, var_name, is_output=False):
        return var_name

    def cpp_method_call_invoke(self, call_name, call_args, is_constructor, attr_type):
        out = super(PrimitiveTypeInfo, self).cpp_method_call_invoke(call_name, call_args, is_constructor, attr_type)
        if self.cpptype == "void":
            out = re.sub("^.+ ret = ", "", out)
        return out

    def cpp_method_return(self, is_constructor):
        if self.cpptype == "void":
            return "return { Error::Code::StsOk, NULL };"
        return super(PrimitiveTypeInfo, self).cpp_method_return(is_constructor)

    def __str__(self):
        return "Primitive(%s)" % (self.cpptype)


class SimpleClassTypeInfo(TypeInfo):
    def __init__(self, gen, typeid):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        """
        super(SimpleClassTypeInfo, self).__init__(gen, typeid)
        self.ci = gen.get_class(self.typeid)
        if self.ci and self.ci.is_ignored:
            self.is_ignored = True
        if self.ci:
            self.rust_full = ("crate::" if self.ci.module not in static_modules else "") + self.ci.module + "::" + self.rust_local
            if self.ci.get_manual_declaration_tpl("rust") is None:
                self.cpp_extern = self.ci.fullname
                self.c_safe_id = self.rust_local
            else:
                self.cpp_extern = "{}Wrapper".format(self.ci.name)
                self.c_safe_id = self.cpp_extern
            self.rust_extern = self.rust_full
            self.is_copy = True

    def cpp_method_return(self, is_constructor):
        if self.cpp_extern.endswith("Wrapper"):
            return "return {{ Error::Code::StsOk, NULL, *reinterpret_cast<{}*>(&ret) }};".format(self.cpp_extern)
        return super(SimpleClassTypeInfo, self).cpp_method_return(is_constructor)

    def __str__(self):
        return "%s (simple)"%(self.cpptype)


class CallbackTypeInfo(TypeInfo):
    def __init__(self, gen, typeid):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        """
        super(CallbackTypeInfo, self).__init__(gen, typeid)
        self.ci = gen.get_class(self.typeid)
        if self.ci and self.ci.is_ignored:
            self.is_ignored = True
        if self.ci:
            self.rust_full = ("crate::" if self.ci.module not in static_modules else "") + self.ci.module + "::" + self.rust_local
            self.cpp_extern = self.ci.fullname
            self.c_safe_id = self.rust_local
            self.rust_extern = "{}Extern".format(self.rust_full)

    def rust_arg_func_decl(self, var_name, is_output=False):
        callback_info = self.gen.get_callback(self.typeid)
        if callback_info is None or callback_info.is_ignored:
            return super(CallbackTypeInfo, self).rust_arg_func_decl(var_name, is_output)
        return "{}: Option<Box<{}>>".format(var_name, self.rust_full)

    def rust_arg_pre_call(self, var_name, is_output=False):
        callback_info = self.gen.get_callback(self.typeid)
        if callback_info is None or callback_info.is_ignored:
            return super(CallbackTypeInfo, self).rust_generic_decl()
        extern_args = []
        rust_args = []
        for arg in callback_info.args:
            extern_args.append(arg.type.rust_extern_arg_func_decl(arg.rsname, arg.is_output()))
            if arg.name != "userdata":
                rust_args.append(arg.type.rust_arg_func_decl(arg.rsname, arg.is_output()))
        return "callback_arg!({}({}) via userdata => ({}))".format(var_name, ", ".join(extern_args), ", ".join(rust_args))

    def __str__(self):
        return "{} (callback)".format(self.cpptype)


class BoxedClassTypeInfo(TypeInfo):
    def __init__(self, gen, typeid):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        """
        super(BoxedClassTypeInfo, self).__init__(gen, typeid)
        self.ci = gen.get_class(self.typeid)
        self.cpptype = self.ci.fullname
        self.rust_extern = "*mut c_void"
        self.rust_full = ("crate::" if self.ci.module not in static_modules else "") + self.ci.module + "::" + self.rust_local
        self.is_by_ptr = True
        self.is_trait = self.typeid in forced_class_trait or self.ci.is_trait
        self.cpp_extern = "void*"
        self.c_safe_id = "void_X"
        self.is_ignored = self.ci.is_ignored
        self.rust_safe_id = self.ci.name

    def cpp_method_call_name(self, method_name):
        return "reinterpret_cast<{}*>(instance)->{}".format(self.cpptype, method_name)

    def cpp_method_call_invoke(self, call_name, call_args, is_constructor, attr_type):
        if is_constructor:
            return "{}* ret = new {}({});".format(self.cpptype, call_name, call_args)
        return super(BoxedClassTypeInfo, self).cpp_method_call_invoke(call_name, call_args, is_constructor, attr_type)

    def __str__(self):
        return "%s (boxed)"%(self.typeid)


class VectorTypeInfo(TypeInfo):
    TEMPLATES = {
        "rust_common": template("""
                #[allow(dead_code)]
                pub struct ${rust_local} {
                    pub(crate) ptr: ${rust_extern}
                }
                
                extern "C" {
                   #[doc(hidden)] fn cv_${rust_safe_id}_new() -> ${rust_extern};
                   #[doc(hidden)] fn cv_${rust_safe_id}_clone(src: ${rust_extern}) -> ${rust_extern};
                   #[doc(hidden)] fn cv_${rust_safe_id}_delete(vec: ${rust_extern});
                   #[doc(hidden)] fn cv_${rust_safe_id}_reserve(vec: ${rust_extern}, n: size_t);
                   #[doc(hidden)] fn cv_${rust_safe_id}_capacity(vec: ${rust_extern}) -> size_t;
                   #[doc(hidden)] fn cv_${rust_safe_id}_push_back(vec: ${rust_extern}, val_ref: *const c_void);
                   #[doc(hidden)] fn cv_${rust_safe_id}_size(vec: ${rust_extern}) -> size_t;
                   #[doc(hidden)] fn cv_${rust_safe_id}_get(vec: ${rust_extern}, index: size_t) -> ${rust_extern};
                }
                
                impl ${rust_local} {
                    pub fn as_raw_${rust_local}(&self) -> ${rust_extern} { self.ptr }

                    pub fn new() -> Self {
                        unsafe { Self { ptr: cv_${rust_safe_id}_new() } }
                    }
                    
                    pub fn with_capacity(capacity: size_t) -> Self {
                        let mut out = Self::new();
                        out.reserve(capacity);
                        out
                    } 
                    
                    pub fn len(&self) -> size_t {
                        unsafe { cv_${rust_safe_id}_size(self.ptr) }
                    }
                    
                    pub fn capacity(&self) -> size_t {
                        unsafe { cv_${rust_safe_id}_capacity(self.ptr) }
                    }
                    
                    pub fn reserve(&mut self, additional: size_t) {
                        unsafe { cv_${rust_safe_id}_reserve(self.ptr, self.len() + additional) }
                    }
                }

                impl Drop for $rust_local {
                    fn drop(&mut self) {
                        unsafe { cv_${rust_safe_id}_delete(self.ptr) };
                    }
                }
            """),

        "rust_boxed": template("""
                // BoxedClassTypeInfo
                impl ${rust_local} {
                    pub fn push(&mut self, val: ${inner_rust_full}) {
                        unsafe { cv_${rust_safe_id}_push_back(self.ptr, val.ptr) }
                    }
                    
                    pub fn get(&self, index: size_t) -> ${inner_rust_full} {
                        ${inner_rust_full} { ptr: unsafe { cv_${rust_safe_id}_get(self.ptr, index) } }
                    }
                    
                    pub fn get_mut(&mut self, index: size_t) -> ${inner_rust_full} {
                        ${inner_rust_full} { ptr: unsafe { cv_${rust_safe_id}_get(self.ptr, index) } }
                    }
                    
                    pub fn to_vec(&self) -> Vec<$inner_rust_full> {
                        (0..self.len()).map(|x| self.get(x)).collect()
                    }
                }
            """),

        "rust_non_boxed": template("""
                impl ${rust_local} {
                    pub fn push(&mut self, val: ${inner_rust_full}) {
                        unsafe { cv_${rust_safe_id}_push_back(self.ptr, &val as *const _ as _) }
                    }
                    
                    pub fn get(&self, index: size_t) -> &$inner_rust_full {
                        unsafe { (cv_${rust_safe_id}_get(self.ptr, index) as *mut ${inner_rust_full}).as_mut().unwrap() }
                    }

                    pub fn get_mut(&mut self, index: size_t) -> &mut $inner_rust_full {
                        unsafe { (cv_${rust_safe_id}_get(self.ptr, index) as *mut ${inner_rust_full}).as_mut().unwrap() }
                    }
                }
            """),

        "rust_non_bool": template("""
                extern "C" { #[doc(hidden)] fn cv_${rust_safe_id}_data(ptr: ${rust_extern}) -> ${rust_extern}; }
                
                impl ::std::ops::Deref for ${rust_local} {
                    type Target = [${inner_rust_full}];
                    
                    fn deref(&self) -> &Self::Target {
                        unsafe {
                            let length = cv_${rust_safe_id}_size(self.ptr);
                            let data = cv_${rust_safe_id}_data(self.ptr);
                            ::std::slice::from_raw_parts(::std::mem::transmute(data), length)
                        }
                    }
                }
            """),

        "cpp_externs": template("""
                    ${cpp_extern} cv_${rust_safe_id}_new() {
                        return new ${cpptype}();
                    }
                    
                    ${cpp_extern} cv_${rust_safe_id}_clone(${cpp_extern} src) {
                        return new ${cpptype}(*reinterpret_cast<${cpptype}*>(src));
                    }
                    
                    void cv_${rust_safe_id}_delete(${cpp_extern} vec) {
                        delete reinterpret_cast<${cpptype}*>(vec);
                    }
                    
                    void cv_${rust_safe_id}_reserve(${cpp_extern} vec, size_t n) {
                        reinterpret_cast<${cpptype}*>(vec)->reserve(n);
                    }

                    size_t cv_${rust_safe_id}_capacity(${cpp_extern} vec) {
                        return reinterpret_cast<${cpptype}*>(vec)->capacity();
                    }
                    
                    void cv_${rust_safe_id}_push_back(${cpp_extern} vec, void* val_ref) {
                        ${inner_cpptype}* val = reinterpret_cast<${inner_cpptype}*>(val_ref);
                        reinterpret_cast<${cpptype}*>(vec)->push_back(*val);
                    }
                    
                    size_t cv_${rust_safe_id}_size(${cpp_extern} vec) {
                        return reinterpret_cast<${cpptype}*>(vec)->size();
                    }
            """),

        "cpp_externs_bool": template("""

                ${inner_cpptype}* cv_${rust_safe_id}_get(${cpp_extern} vec, size_t index) {
                    ${inner_cpptype} val = reinterpret_cast<${cpptype}*>(vec)->at(index);
                    return new ${inner_cpptype}(val);
                }
            """),

        "cpp_externs_non_bool": template("""

                ${inner_cpptype}* cv_${rust_safe_id}_get(${cpp_extern} vec, size_t index) {
                    ${inner_cpptype} val = reinterpret_cast<${cpptype}*>(vec)->at(index);
                    return new ${inner_cpptype}(val);
                }
                
                ${cpp_extern}* cv_${rust_safe_id}_data(${cpp_extern} vec) {
                    return reinterpret_cast<${cpp_extern}*>(reinterpret_cast<${cpptype}*>(vec)->data());
                }
            """),

    }

    def __init__(self, gen, typeid, inner):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        """
        super(VectorTypeInfo, self).__init__(gen, typeid)
        self.is_by_ptr = True
        self.inner = inner
        if isinstance(self.inner, RawPtrTypeInfo):  # fixme, lifetimes required
            self.is_ignored = True
        else:
            self.is_ignored = inner.is_ignored
        if not self.is_ignored:
            self.cpp_extern = "void*"
            self.c_safe_id = "void_X"
            self.cpptype = "std::vector<%s>" % (inner.cpptype)
            self.rust_safe_id = self.rust_local = "VectorOf"+inner.rust_safe_id
            self.rust_full = "types::" + self.rust_local
            self.rust_extern = "*mut c_void"

    def gen_wrappers(self):
        template_vars = combine_dicts(self.__dict__, {
            "inner_cpptype": self.inner.cpptype,
            "inner_rust_full": self.inner.rust_full,
        })

        def write_rust(f):
            f.write(VectorTypeInfo.TEMPLATES["rust_common"].substitute(template_vars))
            if isinstance(self.inner, BoxedClassTypeInfo) or self.inner.is_by_ptr:
                f.write(VectorTypeInfo.TEMPLATES["rust_boxed"].substitute(template_vars))
            else:
                f.write(VectorTypeInfo.TEMPLATES["rust_non_boxed"].substitute(template_vars))
                if self.inner.typeid != "bool":
                    f.write(VectorTypeInfo.TEMPLATES["rust_non_bool"].substitute(template_vars))

        write_exc("{}/{}.type.rs".format(self.gen.rust_dir, self.rust_safe_id), write_rust)
        externs = VectorTypeInfo.TEMPLATES["cpp_externs"].substitute(template_vars)
        if self.inner.typeid == "bool":
            externs += VectorTypeInfo.TEMPLATES["cpp_externs_bool"].substitute(template_vars)
        else:
            externs += VectorTypeInfo.TEMPLATES["cpp_externs_non_bool"].substitute(template_vars)
        write_exc(
            "{}/{}.type.cpp".format(self.gen.cpp_dir, self.rust_safe_id),
            lambda f: f.write(T_CPP_MODULE.substitute(code=externs, includes=""))
        )

    def __str__(self):
        return "Vector[%s]" % (self.inner)


class SmartPtrTypeInfo(TypeInfo):
    TEMPLATES = {
        "rust": template("""
                extern "C" {
                    #[doc(hidden)] fn cv_${rust_safe_id}_get(ptr: ${rust_extern}) -> ${rust_extern};
                    #[doc(hidden)] fn cv_${rust_safe_id}_delete(ptr: ${rust_extern});
                }

                #[allow(dead_code)]
                pub struct ${rust_local} {
                    pub(crate) ptr: ${rust_extern}
                }

                impl ${rust_local} {
                    pub fn as_raw_${rust_safe_id}(&self) -> ${rust_extern} { self.ptr }
                    pub unsafe fn from_raw_ptr(ptr: ${rust_extern}) -> Self {
                        ${rust_local} {
                            ptr
                        }
                    }
                }

                impl Drop for ${rust_local} {
                    fn drop(&mut self) {
                        unsafe { cv_${rust_safe_id}_delete(self.ptr) };
                    }
                }
            """),

        "rust_trait_cast": template("""
                impl ${base_full} for ${rust_local} {
                    fn as_raw_${base_local}(&self) -> ${rust_extern} {
                        unsafe { cv_${rust_safe_id}_get(self.ptr) }
                    }
                }
                
            """),

        "cpp_externs": template("""
                void* cv_${rust_safe_id}_get(${cpp_extern} ptr) {
                    return reinterpret_cast<${cpptype}*>(ptr)->get();
                }
                void  cv_${rust_safe_id}_delete(${cpp_extern} ptr) {
                    delete reinterpret_cast<${cpptype}*>(ptr);
                }
            """),
    }

    def __init__(self, gen, typeid, inner):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        :type inner: TypeInfo
        """
        super(SmartPtrTypeInfo, self).__init__(gen, typeid)
        self.is_by_ptr = True
        self.inner = inner
        self.is_ignored = self.inner.is_ignored
        if not self.is_ignored:
            self.cpp_extern = "void*"
            self.c_safe_id = "void_X"
            self.rust_extern = "*mut c_void"
            self.cpptype = "Ptr<{}>".format(self.inner.cpptype)
            self.rust_local = self.rust_safe_id = "PtrOf{}".format(inner.rust_safe_id)
            self.rust_full = "types::{}".format(self.rust_local)

    def gen_wrappers(self):
        def write_rust(f):
            f.write(SmartPtrTypeInfo.TEMPLATES["rust"].substitute(self.__dict__))
            if not isinstance(self.inner, PrimitiveTypeInfo) and self.inner.ci.is_trait:
                bases = self.gen.all_bases(self.inner.ci.name).union({self.inner.typeid})
                for base in bases:
                    cibase = self.gen.get_type_info(base)
                    if not isinstance(cibase, UnknownTypeInfo):
                        f.write(SmartPtrTypeInfo.TEMPLATES["rust_trait_cast"].substitute(
                            rust_local=self.rust_local,
                            rust_safe_id=self.rust_safe_id,
                            rust_extern=self.rust_extern,
                            base_local=cibase.rust_local,
                            base_full=cibase.rust_full
                        ))

        write_exc("{}/{}.type.rs".format(self.gen.rust_dir, self.rust_safe_id), write_rust)
        write_exc(
            "{}/{}.type.cpp".format(self.gen.cpp_dir, self.rust_safe_id),
            lambda f: f.write(T_CPP_MODULE.substitute(code=SmartPtrTypeInfo.TEMPLATES["cpp_externs"].substitute(self.__dict__), includes=""))
        )

    def __str__(self):
        return "SmartPtr[%s]" % (self.inner)


class RawPtrTypeInfo(TypeInfo):
    def __init__(self, gen, typeid, inner):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        :type inner: TypeInfo
        """
        super(RawPtrTypeInfo, self).__init__(gen, typeid)
        self.inner = inner
        if self.inner.is_ignored or isinstance(self.inner, RawPtrTypeInfo):  # fixme double pointer
            self.is_ignored = True
        else:
            if self.inner.is_by_ptr:
                self.is_by_ptr = self.inner.is_by_ptr
                self.c_safe_id = self.inner.c_safe_id
                self.cpptype = self.inner.cpptype
                self.cpp_extern = self.inner.cpp_extern
                self.rust_safe_id = self.inner.rust_safe_id
                self.rust_local = self.inner.rust_local
                self.rust_full = self.inner.rust_full
                self.rust_extern = self.inner.rust_extern
            else:
                # self.rust_lifetimes = "'b"
                self.rust_safe_id = self.inner.rust_safe_id + "_X"
                self.c_safe_id = self.inner.c_safe_id + "_X"
                self.cpptype = self.inner.cpptype + "*"
                self.cpp_extern = self.inner.cpptype + "*"
                # self.is_by_ptr = True
                self.rust_full = "&"
                self.rust_extern = "*"
                if self.is_const:
                    self.rust_extern += "const "
                else:
                    self.rust_full += "mut "
                    self.rust_extern += "mut "
                if isinstance(self.inner, PrimitiveTypeInfo) and self.inner.cpptype == "void":
                    self.rust_full += "c_void"
                    self.rust_extern += "c_void"
                elif self.is_string():
                    self.rust_full = "String"
                    self.rust_extern += "c_char"
                else:
                    self.rust_full += self.inner.rust_full
                    self.rust_extern += self.inner.rust_extern
            if self.is_const:
                self.c_safe_id = "const_" + self.c_safe_id
                self.cpptype = "const " + self.cpptype
                self.cpp_extern = "const " + self.cpp_extern
                self.rust_safe_id = "const_" + self.rust_safe_id

    def is_string(self):
        return isinstance(self.inner, PrimitiveTypeInfo) and self.inner.cpptype == "char"

    def rust_arg_func_decl(self, var_name, is_output=False):
        if self.is_string():
            return "{}: &{}str".format(var_name, "mut " if is_output else "")
        return super(RawPtrTypeInfo, self).rust_arg_func_decl(var_name, is_output or not self.is_const)

    def rust_arg_pre_call(self, var_name, is_output=False):
        if self.is_string():
            return "string_arg!({})".format(var_name)
        return super(RawPtrTypeInfo, self).rust_arg_pre_call(var_name, is_output)

    def rust_arg_func_call(self, var_name, is_output=False):
        if self.is_string():
            if self.is_const:
                return "{}.as_ptr()".format(var_name)
            return "{}.as_ptr() as _".format(var_name)  # fixme: use as_mut_ptr() when it's stabilized
        return super(RawPtrTypeInfo, self).rust_arg_func_call(var_name, is_output)

    def cpp_arg_func_call(self, var_name, is_output=False):
        if isinstance(self.inner, PrimitiveTypeInfo):
            return var_name
        if self.is_by_ptr:
            return "reinterpret_cast<{}*>({})".format(self.cpptype, var_name)
        return "reinterpret_cast<{}*>(&{})".format(self.inner.cpptype, var_name)

    def cpp_method_call_invoke(self, call_name, call_args, is_constructor, attr_type):
        if self.is_by_ptr:
            return "{}* ret = {}({});".format(self.cpptype, call_name, call_args)
        return super(RawPtrTypeInfo, self).cpp_method_call_invoke(call_name, call_args, is_constructor, attr_type)

    def cpp_method_return(self, is_constructor):
        if self.is_string():
            return "return { Error::Code::StsOk, NULL, strdup(ret) };"
        return super(RawPtrTypeInfo, self).cpp_method_return(is_constructor)

    def __str__(self):
        return "RawPtr[%s]" % (self.inner)


class UnknownTypeInfo(TypeInfo):
    def __init__(self, gen, typeid):
        """
        :type gen: RustWrapperGenerator
        :type typeid: str
        """
        super(UnknownTypeInfo, self).__init__(gen, typeid)
        self.is_ignored = True
        logging.info("Registering an unknown type: %s", self.typeid)

    def __str__(self):
        return "Unknown[%s]" % (self.typeid)


def parse_type(gen, typeid):
    """
    :type gen: RustWrapperGenerator
    :type typeid: str
    :rtype: TypeInfo
    """
    typeid = typeid.strip()
    full_typeid = typeid
    is_const = False
    if full_typeid.startswith("const "):
        typeid = full_typeid[6:]
        is_const = True
    if typeid == "":
        typeid = "void"
        full_typeid = "void"
    # if typeid.endswith("&"):
    #     return ReferenceTypeInfo(gen, typeid, gen.get_type_info(typeid[0:-1]))
    is_by_ref = False
    if typeid.endswith("&"):
        typeid = typeid[:-1].strip()
        is_by_ref = True
    if typeid in primitives:
        return PrimitiveTypeInfo(gen, full_typeid)
    elif typeid.endswith("*"):
        return RawPtrTypeInfo(gen, full_typeid, gen.get_type_info(typeid[:-1].strip()))
    elif typeid.endswith("[]"):
        return RawPtrTypeInfo(gen, full_typeid, gen.get_type_info(typeid[:-2].strip()))
    elif typeid in ("string", "String", "std::string", "cv::String"):
        return StringTypeInfo(gen, full_typeid)
    elif typeid == "":
        raise NameError("empty type detected")
    elif typeid.startswith("Ptr<"):
        return SmartPtrTypeInfo(gen, full_typeid, gen.get_type_info(typeid[4:-1].strip()))
    #        return RawPtrTypeInfo(gen, full_typeid, gen.get_type_info(typeid[4:-1]))
    elif typeid.startswith("vector<"):
        inner = gen.get_type_info(typeid[7:-1].strip())
        if not inner:
            raise NameError("inner type `%s' not found" % (typeid[7:-1].strip()))
        return VectorTypeInfo(gen, full_typeid, inner)
    elif typeid.startswith("std::vector<"):
        inner = gen.get_type_info(typeid[12:-1].strip())
        if not inner:
            raise NameError("inner type `%s' not found" % (typeid[12:-1].strip()))
        return VectorTypeInfo(gen, full_typeid, inner)
    else:
        ci = gen.get_class(typeid)
        if ci and not ci.is_ignored:
            reconst_full_typeid = "{}{}{}".format("const " if is_const else "", ci.fullname, "&" if is_by_ref else "")
            if ci.is_simple:
                return SimpleClassTypeInfo(gen, reconst_full_typeid)
            elif ci.is_callback:
                return CallbackTypeInfo(gen, reconst_full_typeid)
            else:
                return BoxedClassTypeInfo(gen, reconst_full_typeid)
        actual = type_replace.get(typeid)
        if actual:
            ci = gen.get_class(actual)
            if ci:
                reconst_full_typeid = "{}{}{}".format("const " if is_const else "", ci.fullname, "&" if is_by_ref else "")
                if ci.is_simple:
                    return SimpleClassTypeInfo(gen, reconst_full_typeid)
                elif ci.is_callback:
                    return CallbackTypeInfo(gen, reconst_full_typeid)
                else:
                    return BoxedClassTypeInfo(gen, reconst_full_typeid)
            return parse_type(gen, actual)
    return UnknownTypeInfo(gen, full_typeid)

#
#       GENERATOR
#


class RustWrapperGenerator(object):
    TEMPLATES = {
        "simple_class": {
            "rust_struct": template("""
                    ${doc_comment}
                    #[repr(C)]
                    #[derive(Copy,Clone,Debug,PartialEq)]
                    pub struct ${rust_local} {
                    ${fields}
                    }
                    
                """),

            "rust_struct_simple": template("""
                    ${doc_comment}
                    #[repr(C)]
                    #[derive(Copy,Clone,Debug,PartialEq)]
                    pub struct ${rust_local} (${fields});
                    
                """),

            "cpp_struct": template("""
                    typedef struct ${c_safe_id} {
                    ${fields}
                    } ${c_safe_id};
                    
                """),

            "rust_field_array": template("""${visibility}${rsname}: [${rust_full}; ${size}],\n"""),

            "rust_field_non_array": template("""${visibility}${rsname}: ${rust_full},\n"""),

            "cpp_field_array": template("""${cpp_extern} ${name}[${size}];\n"""),

            "cpp_field_non_array": template("""${cpp_extern} ${name};\n"""),
        },
    }

    def __init__(self):
        self.cpp_dir = ""
        self.rust_dir = ""
        self.classes = OrderedDict()  # type: dict[str, ClassInfo]
        self.functions = []
        self.ported_func_list = []
        self.skipped_func_list = []
        self.consts = []
        self.type_infos = {}
        self.callbacks = []  # type: list[CallbackInfo]
        self.namespaces = set()
        self.generated = set()
        self.generated_functions = []
        self.func_names = set()

    def get_class(self, classname):
        """
        :type classname: str
        :rtype: ClassInfo
        """
        c = self.classes.get(classname)
        if c:
            return c
        for c in self.classes.values():
            if classes_equal(classname, c.fullname):
                return c
        return None

    def set_type_info(self, typeid, type_info):
        typeid = typeid.strip()
        self.type_infos[typeid] = type_info

    def get_type_info(self, typeid):
        """
        :type typeid: str
        :rtype: TypeInfo
        """
        typeid = typeid.strip()
        if typeid not in self.type_infos:
            self.type_infos[typeid] = parse_type(self, typeid)
        return self.type_infos[typeid]

    def get_const(self, name):
        """
        :type name: str
        :rtype: ConstInfo
        """
        for c in self.consts:
            if c.cname == name:
                return c
        return None

    def get_callback(self, name):
        """
        :type name: str
        :rtype: CallbackInfo
        """
        for x in self.callbacks:
            if x.fullname == name:
                return x
        return None

    def add_decl(self, module, decl):
        decl = decl_patch(module, decl)
        if decl[0] == "cv.String.String" or decl[0] == 'cv.Exception.~Exception':
            return
        if decl[0] == "cv.Algorithm":
            decl[0] = "cv.Algorithm.Algorithm"
        name = decl[0]  # type: str
        if name.startswith("struct") or name.startswith("class"):
            self.add_class_decl(module, decl)
        elif name.startswith("const"):
            self.add_const_decl(module, decl)
        elif name.startswith("typedef"):
            self.add_typedef_decl(module, decl)
        elif name.startswith("callback"):
            self.add_callback_decl(module, decl)
        else:
            self.add_func_decl(module, decl)

    def add_class_decl(self, module, decl):
        item = ClassInfo(self, module, decl, frozenset(self.namespaces))
        # register
        logging.info("register class %s (%s)%s%s", item.fullname, decl,
                     " [ignored]" if item.is_ignored else "",
                     " impl:"+",".join(item.bases) if len(item.bases) else "")
        self.classes[item.fullname] = item

    def add_const_decl(self, _module, decl):
        item = ConstInfo(self, decl, frozenset(self.namespaces))
        # register
        if item.is_ignored():
            logging.info('ignored: %s', item)
        elif not self.get_const(item.name):
            self.consts.append(item)

    def add_typedef_decl(self, _module, decl):
        item = TypedefInfo(self, decl, frozenset(self.namespaces))
        if not isinstance(item.alias_typ(), UnknownTypeInfo) and isinstance(item.typ(), UnknownTypeInfo):
            self.set_type_info(item.name, item.alias_typ())

    def add_callback_decl(self, module, decl):
        item = CallbackInfo(self, decl, frozenset(self.namespaces))
        if not item.is_ignored:
            self.add_decl(module, ("class {}".format(item.fullname.replace("::", ".")), "", ["/Ghost", "/Callback"], []))
            self.callbacks.append(item)

    def add_func_decl(self, module, decl):
        item = FuncInfo(self, module, decl, frozenset(self.namespaces))
        if not item.is_ignored:
            # register self to class or generator
            if item.kind == item.KIND_FUNCTION:
                self.register_function(item)
            else:
                item.ci.add_method(item)

    def register_function(self, f):
        logging.info("register %s %s (%s)"%(f.kind, f.name, f.identifier))
        self.functions.append(f)

    def gen(self, srcfiles, module, cpp_dir, rust_dir):
        """
        :param srcfiles:
        :type module: str
        :type cpp_dir: str
        :type rust_dir: str
        :return:
        """
        self.cpp_dir = cpp_dir
        self.rust_dir = rust_dir
        includes = []

        parser = hdr_parser.CppHeaderParser()
        self.namespaces = set(x for x in parser.namespaces)
        self.namespaces.add("cv")

        for m, decls in decls_manual_pre.items():
            for decl in decls:
                logging.info("\n--- Manual ---\n%s", pformat(decl, 4))
                self.add_decl(m, decl)

        for hdr in srcfiles:
            decls = parser.parse(hdr, False)
            self.namespaces = set(str(x.replace(".", "::")) for x in parser.namespaces)
            logging.info("\n\n=============== Header: %s ================\n\n", hdr)
            logging.info("Namespaces: %s", parser.namespaces)
            logging.info("Comment: %s", parser.module_comment)
            includes.append('#include "' + hdr + '"')
            for decl in decls:
                logging.info("\n--- Incoming ---\n%s", pformat(decl, 4))
                self.add_decl(module, decl)

        for m, decls in decls_manual_post.items():
            for decl in decls:
                logging.info("\n--- Manual ---\n%s", pformat(decl, 4))
                self.add_decl(m, decl)

        logging.info("\n\n===== Generating... =====")
        self.moduleCppTypes = StringIO()
        self.moduleCppCode = StringIO()
        self.moduleCppConsts = StringIO()
        self.moduleSafeRust = StringIO()
        self.moduleRustExterns = StringIO()

        module_comment = self.reformat_doc(parser.module_comment.get(module, ""), None, "//!")
        self.moduleSafeRust.write(module_comment)

        self.moduleSafeRust.write(template("""
            use std::os::raw::{c_char, c_void};
            use libc::size_t;
            use crate::{Error, Result, """ + ", ".join(static_modules) + """};
            
        """).substitute())
        for co in sorted(self.consts, key=lambda c: c.rustname):
            rust = co.gen_rust()
            if rust:
                self.moduleSafeRust.write(rust)
            else:
                self.moduleCppConsts.write(co.gen_cpp_for_complex())

        self.moduleSafeRust.write("\n")

        for cb in self.callbacks:
            self.gen_callback(cb)

        for t in list(self.type_infos.values()):
            if not t.is_ignored:
                t.gen_wrappers()

        for c in list(self.classes.values()):
            if c.is_simple and not c.is_ignored and not c.is_ghost and c.module == module:
                self.gen_simple_class(c)

        for fi in sorted(self.functions, key=lambda fi: fi.identifier):
            if not fi.is_ignored:
                self.gen_func(fi)

        for ci in sorted(list(self.classes.values()), key=lambda ci:ci.fullname):
            self.gen_class(ci)

        with open("{}/{}.types.h".format(cpp_dir, module), "w") as f:
            f.write(self.moduleCppTypes.getvalue())

        with open("{}/{}.consts.cpp".format(cpp_dir, module), "w") as f:
            f.write("""#include <cstdio>\n""")
            f.write("""#include "opencv2/opencv_modules.hpp"\n""")
            f.write("""#include "opencv2/%s.hpp"\n"""%(module))
            for include in includes:
                f.write(include+"\n")
            f.write("""using namespace cv;\n""")
            f.write("int main(int, char**) {\n")
            f.write(self.moduleCppConsts.getvalue())
            f.write("}\n")

        namespaces = ""
        for namespace in self.namespaces:
            if namespace != "":
                namespaces += "using namespace %s;\n"%(namespace.replace(".", "::"))
        with open("{}/{}.cpp".format(cpp_dir, module), "w") as f:
            f.write(T_CPP_MODULE.substitute(m=module, M=module.upper(), code=self.moduleCppCode.getvalue(), includes="\n".join(includes), namespaces=namespaces))

        with open("{}/{}.externs.rs".format(rust_dir, module), "w") as f:
            f.write("extern \"C\" {\n")
            f.write(self.moduleRustExterns.getvalue())
            f.write("}\n")

        with open("{}/{}.rs".format(rust_dir, module), "w") as f:
            f.write(self.moduleSafeRust.getvalue())

        with open("{}/{}.txt".format(cpp_dir, module), "w") as f:
            f.write(self.make_report())

    def make_report(self):
        """
        Returns string with generator report
        """
        report = StringIO()
        total_count = len(self.ported_func_list)+len(self.skipped_func_list)
        report.write("FOUND FUNCs: %i\n\n" % (total_count))
        report.write("PORTED FUNCs: %i\n\n" % (len(self.ported_func_list)))
        for f in self.ported_func_list:
            report.write("PORTED: " + f + "\n")
        if len(self.skipped_func_list) > 0:
            report.write("\n\nSKIPPED FUNCs: %i\n\n" % (len(self.skipped_func_list)))
            for f in self.skipped_func_list:
                report.write("SKIPPED: " + f + "\n")
        return report.getvalue()

    def class_is_ignored(self, type_name):
        for c in class_ignore_list:
            if re.match(c, type_name):
                return True
        return False

    def gen_vector_struct_for(self, name):
        struct_name = "cv_vector_of_"+name
        self.defined_in_types_h.appand(struct_name)
        self.moduleCppTypes.write

    def gen_func(self, fi):
        """
        :type fi: FuncInfo
        :return:
        """
        if fi.kind == fi.KIND_FUNCTION or fi.attr_accessor_type:
            for item in self.generated_functions:
                if item.fullname == fi.fullname and str(item.args) == str(fi.args):
                    return
            else:
                self.generated_functions.append(fi)
        logging.info("Generating func %s"%(fi.identifier))
        reason = fi.reason_to_skip()
        if reason:
            logging.info("  ignored: " + reason)
            self.skipped_func_list.append("%s\n   %s\n"%(fi,reason))
            return
        self.ported_func_list.append(fi.__repr__())
        self.generated.add(fi.identifier)

        # C function prototype
        self.moduleCppCode.write(fi.gen_cpp())

        # rust's extern C
        self.moduleRustExterns.write(fi.gen_rust_extern())

        # Here we filter and rename functions with duplicate names.
        # If duplicate functions have different call arguments
        # we generate new name for duplicate function, to allow
        # to call it from rust code.
        # If duplicate functions have the same call arguments, we skip duplicate function.
        rust_func_name = fi.r_name()
        classname = "" if fi.kind == fi.KIND_FUNCTION else fi.classname
        renamed = False
        while classname + '::' + rust_func_name in self.func_names:
            rust_func_name = bump_counter(rust_func_name)
            renamed = True
        if renamed:
            func_rename[fi.identifier] = rust_func_name

        # rust safe wrapper
        self.moduleSafeRust.write(fi.gen_safe_rust())
        self.func_names.add(classname + '::' + fi.r_name())

    def get_value_struct_field(self, name, typ):
        rsname = camel_case_to_snake_case(reserved_rename.get(name, name))
        visibility = "" if rsname == "__rust_private" else "pub "
        templates = RustWrapperGenerator.TEMPLATES["simple_class"]
        if "[" in typ:
            bracket = typ.index("[")
            size = typ[bracket+1:-1]
            typ = self.get_type_info(typ[:bracket])
            out_cpp = templates["cpp_field_array"].substitute(cpp_extern=typ.cpp_extern, name=name, size=size)
            out_rust = templates["rust_field_array"].substitute(visibility=visibility, rsname=rsname, rust_full=typ.rust_full, size=size)
        else:
            typ = self.get_type_info(typ)
            out_cpp = templates["cpp_field_non_array"].substitute(cpp_extern=typ.cpp_extern, name=name)
            out_rust = templates["rust_field_non_array"].substitute(visibility=visibility, rsname=rsname, rust_full=typ.rust_full)
        return out_rust, out_cpp

    def gen_callback(self, cb):
        """
        :type cb: CallbackInfo
        """
        self.moduleSafeRust.write(cb.gen_rust())

    def gen_simple_class(self, ci):
        """
        :type ci: ClassInfo
        """
        rust_fields = ""
        cpp_fields = ""
        if len(ci.props) > 0:
            for p in ci.props:
                rust_field, cpp_field = self.get_value_struct_field(p.name, p.ctype)
                rust_fields += rust_field
                cpp_fields += cpp_field
        else:
            rust_field, cpp_field = self.get_value_struct_field("__rust_private", "unsigned char[0]")
            rust_fields += rust_field
            cpp_fields += cpp_field

        templ = ci.get_manual_declaration_tpl("rust")
        if templ is None:
            templ = RustWrapperGenerator.TEMPLATES["simple_class"]["rust_struct"]
        self.moduleSafeRust.write(templ.substitute(combine_dicts(ci.type_info().__dict__, {
            "doc_comment": self.reformat_doc(ci.comment).rstrip(),
            "fields": indent(rust_fields.rstrip()),
        })))
        templ = ci.get_manual_declaration_tpl("cpp")
        if templ is None:
            templ = RustWrapperGenerator.TEMPLATES["simple_class"]["cpp_struct"]
        self.moduleCppTypes.write(templ.substitute(combine_dicts(ci.type_info().__dict__, {
            "fields": indent(cpp_fields.rstrip()),
        })))

    def gen_boxed_class(self, name):
        ci = self.get_class(name)
        if not ci:
            logging.info("type %s not found", name)
            return
        typ = ci.type_info()
        logging.info("Generating box for %s", ci)

        self.moduleCppCode.write(template("""
            // boxed class: $typeid
            void cv_${rust_local}_delete(void* instance) {
                delete ($cpptype*) instance;
            }
            """).substitute(typ.__dict__))

        self.moduleRustExterns.write("#[doc(hidden)] pub fn cv_%s_delete(ptr : *mut c_void);\n" % (typ.rust_local))

        self.moduleSafeRust.write("// boxed class %s\n"%(typ.typeid))
        self.moduleSafeRust.write(self.reformat_doc(ci.comment))
        self.moduleSafeRust.write(template("""
            #[allow(dead_code)]
            pub struct $rust_local {
                #[doc(hidden)] pub(crate) ptr: *mut c_void
            }
            impl Drop for $rust_full {
                fn drop(&mut self) {
                    unsafe { sys::cv_${rust_local}_delete(self.ptr) };
                }
            }
            impl $rust_full {
                pub fn as_raw_${rust_local}(&self) -> *mut c_void { self.ptr }
                pub unsafe fn from_raw_ptr(ptr: ${rust_extern}) -> Self {
                    ${rust_local} {
                        ptr
                    }
                }
            }
            
            """).substitute(typ.__dict__))

        bases = self.all_bases(name)
        for base in bases:
            cibase = self.get_class(base)
            if cibase is not None:
                cibase = cibase.type_info()
                self.moduleSafeRust.write(template("""
                    impl $base_full for ${rust_local} {
                        fn as_raw_$base_local(&self) -> *mut c_void { self.ptr }
                    }
                    
                """).substitute(rust_local=typ.rust_local, base_local=cibase.rust_local, base_full=cibase.rust_full))

    # all your bases...
    def all_bases(self, name):
        bases = set()
        ci = self.get_class(name)
        if ci is not None:
            for b in ci.bases:
                bases.add(b)
                bases = bases.union(self.all_bases(b))
        return bases

    def gen_class(self, ci):
        """
        :type ci: ClassInfo
        :rtype: str
        """
        if ci.is_ignored:
            logging.info("Manual ignore class %s", ci)
            return
        if ci.is_ghost:
            logging.info("Ghost class %s, ignoring", ci)
            return
        t = ci.type_info()
        if not t:
            logging.info("Ignore class %s (not found)", ci)
            return
        if ci.namespace == "":
            logging.info("Not namespaced. Skipped %s", ci)
            return
        if t.is_trait:
            if len(ci.bases):
                bases = (x.rust_full for x in (self.get_type_info(x) for x in ci.bases) if not isinstance(x, UnknownTypeInfo))
                bases = " : " + " + ".join(bases)
            else:
                bases = ""
            logging.info("Generating impl for trait %s", ci)
            self.moduleSafeRust.write("// Generating impl for trait %s\n" % (ci))
            self.moduleSafeRust.write(self.reformat_doc(ci.comment))
            self.moduleSafeRust.write("pub trait %s%s {\n" % (t.rust_local, bases))
            self.moduleSafeRust.write("    #[doc(hidden)] fn as_raw_%s(&self) -> *mut c_void;\n" % (t.rust_local))
            for fi in ci.methods:
                if not fi.is_static:
                    self.gen_func(fi)
            self.moduleSafeRust.write("}\n\n")
            self.moduleSafeRust.write("impl<'a> %s + 'a {\n\n" % (t.rust_local))
            for fi in ci.methods:
                if fi.is_static:
                    self.gen_func(fi)
            self.moduleSafeRust.write("}\n\n")
        else:
            if isinstance(t, BoxedClassTypeInfo):
                self.gen_boxed_class(ci.fullname)
            has_impl = len(ci.methods) > 0 or (isinstance(t, BoxedClassTypeInfo) and len(ci.props) > 0)
            if has_impl:
                logging.info("Generating impl for struct %s", ci)
                self.moduleSafeRust.write("impl %s {\n\n" % (t.rust_local))
            for fi in ci.methods:
                self.gen_func(fi)
            if isinstance(t, BoxedClassTypeInfo):
                for prop in ci.props:
                    attrs = ["/ATTRGETTER"]
                    prop_type = self.get_type_info(prop.ctype)
                    is_const = prop_type.is_const or prop_type.is_copy
                    if is_const:
                        attrs.append("/C")
                    read_func = FuncInfo(
                        self,
                        ci.module,
                        [
                            "{}.{}".format(ci.fullname, prop.name),
                            prop.ctype,
                            attrs,
                            [],
                            None,
                            prop.comment
                        ],
                        self.namespaces)
                    if not read_func.is_ignored and not read_func.rv_type().is_ignored:
                        self.gen_func(read_func)
                        if not is_const:
                            attrs = ["/ATTRSETTER"]
                            write_func = FuncInfo(
                                self,
                                ci.module,
                                [
                                    "{}.set_{}".format(ci.fullname, prop.name),
                                    "void",
                                    attrs,
                                    (
                                        [prop_type.cpptype, "val", "", []],
                                    ),
                                    None,
                                    prop.comment
                                ],
                                self.namespaces
                            )
                            self.gen_func(write_func)
            if has_impl:
                self.moduleSafeRust.write("}\n\n")

    def reformat_doc(self, text, func_info=None, comment_prefix="///"):
        """
        :type text: str
        :type func_info: FuncInfo
        :type comment_prefix: str
        :rtype: str
        """
        # @overload
        if func_info is not None and "@overload" in text:
            try:
                src_comment = next(x.comment for x in self.functions if x.fullname == func_info.fullname and "@overload" not in x.comment and len(x.comment) > 0)
                text = text.replace("@overload", src_comment + "\n\n## Overloaded parameters\n")
            except StopIteration:
                text = text.replace("@overload", "")
        # module titles
        text = re.sub(r"\s*@{.*$", "", text, 0, re.M)
        text = re.sub(r"\s*@}.*$", "", text, 0, re.M)
        text = re.sub(r"@defgroup [^ ]+ (.*)", "# \\1", text)
        text = re.sub(r"^.*?@addtogroup\s+(.+)", "", text, 0, re.M)
        text = text.strip()
        if len(text) == 0:
            return ""
        # remove asterisks from c++ comment delimiters
        text = re.sub(r"^\s*\*$", "", text, 0, re.M)
        text = re.sub(r"^\* ", "", text, 0, re.M)
        # comment body markers
        text = text.replace("@brief", "").replace("@note", "\nNote:")
        # code blocks, don't run them during tests
        text = text.replace("@code", "```ignore").replace("@endcode", "```\n")
        # see also block
        text = re.sub(r"@sa\s+", "## See also\n", text, 1, re.M)
        text = text.replace("@sa", "")
        # citation links
        text = re.sub(r"@cite\s+(.+?)\b", r"[\1](https://docs.opencv.org/3.4.6/d0/de3/citelist.html#CITEREF_\1)", text)
        # images
        text = re.sub(r"!\[(.*?)\]\((?:pics/)?(.+)?\)", r"![\1](https://docs.opencv.org/3.4.6/\2)", text)
        # ?
        text = re.sub(r".*\*\*\*\*\*", "", text, 0, re.M)
        # returns
        text = re.sub(r"^.*?@returns?\s*", "## Returns\n", text, 0, re.M)
        # parameter list
        text = re.sub(r"^(.*?@param)", "## Parameters\n\\1", text, 1, re.M)
        text = re.sub(r"^.*?@param(?:\[in\])?\s+(\w+) *(.*)", r"* \1: \2", text, 0, re.M)
        text = re.sub(r"^.*?@param\s*\[out\]\s+(\w+) *(.*)", r"* \1: [out] \2", text, 0, re.M)
        # deprecated
        m = re.search(r"^.*?@deprecated\s+(.+)", text, re.M)
        deprecated = None
        if m is not None:
            text = re.sub(r"^.*?@deprecated\s+(.+)", r"**Deprecated**: \1\n", text, 0, re.M)
            deprecated = m.group(1)
        # ?
        text = re.sub("^-  (.*)", "*  \\1", text, 0, re.M)
        # math expressions
        # if r"\f" in text:
        #     text = '<script type="text/javascript" src="https://latex.codecogs.com/latexit.js"></script>\n' + text  # fixme, slows down browser a lot
        text = re.sub(r"\\f\[", "<div lang='latex'>", text, 0, re.M)
        text = re.sub(r"\\f\]", "</div>", text, 0, re.M)
        text = re.sub(r"\\f\$(.*?)\\f\$", "<span lang='latex'>\\1</span>", text, 0, re.M)
        # catch sequences of 4 indents and reduce them to avoid cargo test running them as code
        text = re.sub(r"^((\s{1,5})\2{3})(\S)", r"\2\3", text, 0, re.M)
        text = text.strip()
        if len(text) > 0:
            # add rustdoc comment markers
            text = re.sub("^", comment_prefix + " ", text.strip(), 0, re.M) + "\n"
        if deprecated is not None:
            text += "#[deprecated = \"{}\"]\n".format(deprecated)
        return text


def main():
    cpp_dir = sys.argv[2]
    rust_dir = sys.argv[3]
    module = sys.argv[4]
    srcfiles = sys.argv[5:]
    logging.basicConfig(filename='%s/%s.log' % (cpp_dir, module), format=None, filemode='w', level=logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)
    logging.getLogger().addHandler(handler)
    print(("Generating module '" + module + "' from headers:\n\t" + "\n\t".join(srcfiles)))
    generator = RustWrapperGenerator()
    generator.gen(srcfiles, module, cpp_dir, rust_dir)


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(("Usage:\n", \
              os.path.basename(sys.argv[0]), \
              "<full path to hdr_parser.py> <cpp_out_dir> <rust_out_dir> <module name> <C++ header> [<C++ header>...]"))
        print(("Current args are: ", ", ".join(["'"+a+"'" for a in sys.argv])))
        exit(0)

    hdr_parser_path = os.path.abspath(sys.argv[1])
    if hdr_parser_path.endswith(".py"):
        hdr_parser_path = os.path.dirname(hdr_parser_path)
    sys.path.append(hdr_parser_path)
    import hdr_parser
    main()
