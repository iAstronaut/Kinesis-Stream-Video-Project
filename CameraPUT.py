import json
import timeit
from ims_utils.common import get_error_response, get_success_response
from http import HTTPStatus

import jsonschema
from datetime import datetime

import ims_logger
import ims_authen
from ims_authen import ADMIN_ROLE
from ims_utils.model import SETTINGS_SCHEMA
from ims_utils.gateway import update_gw_cameras_shadow, get_gateway_info, update_camera_shadow
from ims_utils.camera import trim_attrs_camera, validate_camera_settings, \
    is_duplicate_resource, get_cam_pre_status, set_resource_settings
from ims_db.gateway_db import get_gateway
from ims_db.camera_db import get_camera, update_camera
from ims_db.model_db import get_model

camera_update_schema = {
    "type": "object",
    "properties": {
        "cameraId": {"type": "string"},
        "cameraName": {"type": "string"},
        "modelId": {"type": "string"},
        "description": {"type": "string"},
        "settings": SETTINGS_SCHEMA,
        "isEnable": {"type": "boolean"},

    },
    "required": ["cameraId", "cameraName", "modelId", "isEnable", "resource"]
}

ACCEPT_ROLES = [ADMIN_ROLE]


def lambda_handler(event, context):
    start = timeit.default_timer()
    author = event["headers"].get("authorization")
    can_access, user_data = ims_authen.authenticate(author, ACCEPT_ROLES)
    if can_access:
        response = main_process(event, user_data)
    else:
        response = ims_authen.FAIL_AUTHEN_RESPONSE
    handling_time = int(1e3 * (timeit.default_timer() - start))
    ims_logger.logging(event, context, user_data, response, handling_time)
    return response


def main_process(event, user_data):
    try:
        data = json.loads(event.get("body"))
        jsonschema.validate(data, camera_update_schema)

        camera_id = data.get("cameraId")
        name = data.get("cameraName")
        model_id = data.get("modelId")
        resource = data.get("resource")
        input_settings = data.get("settings") if data.get("settings") else {}
        description = data.get("description") if data.get("description") else ""
        is_enable = data.get("isEnable")

        exist_camera = get_camera(camera_id)
        if exist_camera is None:
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")
        model = get_model(model_id)
        if (exist_camera.get("modelId") != model_id):
            if model is None:
                return get_error_response(HTTPStatus.NOT_FOUND.value, "E006")

        settings = exist_camera.get("settings")
        settings.update(input_settings)
        set_resource_settings(settings, model.get("connectionType"), resource)
        validate_camera_settings(settings, model)
        gateway = get_gateway(exist_camera.get("gatewayId"))
        _, gw_ip = get_gateway_info(gateway)
        if is_duplicate_resource(settings, gateway, gw_ip, camera_id):
            return get_error_response(HTTPStatus.CONFLICT.value, "E013")
        status = get_cam_pre_status(gateway, model, is_enable)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        update_item = update_camera(camera_id,
                                    update_expression="SET cameraName = :n, "
                                                      "searchName = :sn, "
                                                      "modelId = :t, "
                                                      "description = :d, "
                                                      "settings = :s, "
                                                      "isEnable = :e, "
                                                      "isPTZ = :i, "
                                                      "pipeline = :p, "
                                                      "modifiedTime = :mt, "
                                                      "modifiedBy = :mb, "
                                                      "#st = :st, "
                                                      "#rs = :rs",
                                    attribute_value={":t": model_id,
                                                     ":n": name,
                                                     ":sn": name.lower(),
                                                     ":d": description,
                                                     ":s": settings,
                                                     ":e": is_enable,
                                                     ":i": model.get("isPTZ") == True,
                                                     ":p": model.get("pipeline"),
                                                     ":mt": current_time,
                                                     ":st": status,
                                                     ":rs": resource,
                                                     ":mb": user_data.get("userId")
                                                     },
                                    attribute_name={"#st": "status",
                                                    "#rs": "resource"})
        update_gw_cameras_shadow(update_item.get("gatewayId"), camera_id)
        update_camera_shadow(update_item)
        return get_success_response(HTTPStatus.OK.value, trim_attrs_camera(update_item))
    except jsonschema.exceptions.ValidationError as validate_err:
        message = str(validate_err.message)
        if validate_err.json_path == "$.lowmode":
            message = "Camera model support this lowmode."
        return get_error_response(HTTPStatus.BAD_REQUEST.value, "E003", message)
    except Exception as e:
        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
