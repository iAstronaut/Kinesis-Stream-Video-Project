#!/bin/bash
source /opt/axisapp/gateway/gateway.bash
STREAM_NAME=$(aws kinesisvideo list-streams --region "$AWS_DEFAULT_REGION" --debug | jq -r --arg device "$AWS_IOT_CORE_THING_NAME" '.StreamInfoList[] | select(.DeviceName == $device) | .StreamName')

REGION="$AWS_DEFAULT_REGION"  # Region của bạn

# Kiểm tra kết nối với Kinesis Video Streams
STREAM_STATUS=$(aws kinesisvideo describe-stream --stream-name $STREAM_NAME --region $REGION --query 'StreamInfo.Status' --output text 2>&1)

# In ra giá trị của STREAM_STATUS để kiểm tra
echo "STREAM_STATUS: $STREAM_STATUS"

if [[ "$STREAM_STATUS" == "ACTIVE" ]]; then
    echo "Stream $STREAM_NAME is active."
    return 0
else
    echo "Connection to Kinesis Video Stream failed. Status: $STREAM_STATUS"
    return 1
    
fi
