import timeit
from ims_utils.common import get_error_response, get_success_response
from http import HTTPStatus

import boto3

import ims_logger
import ims_authen

video_client = boto3.client('kinesisvideo')


def lambda_handler(event, context):
    start = timeit.default_timer()
    author = event["headers"].get("authorization")
    can_access, user_data = ims_authen.authenticate(author)
    if can_access:
        response = main_process(event, user_data)
    else:
        response = ims_authen.FAIL_AUTHEN_RESPONSE
    handling_time = int(1e3 * (timeit.default_timer() - start))
    ims_logger.logging(event, context, user_data, response, handling_time)
    return response


def main_process(event, user_data):
    try:
        mode = event['queryStringParameters'].get('mode',"LIVE") #! Chế độ phát (LIVE)
        stream_name = event['queryStringParameters'].get('camera')
        # support 2 mode: ON_DEMAND & LIVE
        if mode == 'ON_DEMAND': #! Chế độ phát (DEMAND) (RECORD)
            start_timestamp = int(event['queryStringParameters'].get('start'))
            end_timestamp = int(event['queryStringParameters'].get('end'))
            frame_selector = {
                'FragmentSelectorType': 'SERVER_TIMESTAMP', #! FragmentSelectorType: Loại selector được sử dụng để chỉ định khoảng thời gian. //SERVER_TIMESTAMP cho biết rằng chúng ta sẽ sử dụng khoảng thời gian dựa trên dấu thời gian của máy chủ.
                'TimestampRange': {
                    'StartTimestamp': start_timestamp,
                    'EndTimestamp': end_timestamp
                }
            }
        else:
            frame_selector = {
                'FragmentSelectorType': 'SERVER_TIMESTAMP',
            }
        expired_time_in_seconds = 43200  # 12 hours #! Thời gian hết hạn của URL phát lại
        if 'queryStringParameters' in event:
            expired_time_in_seconds = int(event['queryStringParameters']['expires']) if 'expires' in event[
                'queryStringParameters'] else expired_time_in_seconds

        response = video_client.get_data_endpoint(StreamName=stream_name, APIName='GET_HLS_STREAMING_SESSION_URL')

        archived_client = boto3.client('kinesis-video-archived-media', endpoint_url=response['DataEndpoint'])
        response = archived_client.get_hls_streaming_session_url(
            StreamName=stream_name,
            PlaybackMode=mode,
            HLSFragmentSelector=frame_selector,
            Expires=expired_time_in_seconds,
            MaxMediaPlaylistFragmentResults=5000,
        )
        stream_url = response['HLSStreamingSessionURL']
        body = {'url': stream_url}
        headers = {
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,GET"
        }
        return get_success_response(HTTPStatus.OK.value, body, headers)
    except Exception as e:
        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
