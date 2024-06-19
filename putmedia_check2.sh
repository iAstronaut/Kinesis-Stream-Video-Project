#!/bin/bash
source /opt/axisapp/gateway/gateway.bash

# Fetch the stream name based on the IoT device name
STREAMS_JSON=$(aws kinesisvideo list-streams --region "$AWS_DEFAULT_REGION" --output json --debug)
echo "Streams JSON: $STREAMS_JSON"

# Extract the stream names based on the device name
STREAM_NAMES=$(echo "$STREAMS_JSON" | jq -r --arg device "$AWS_IOT_CORE_THING_NAME" '.StreamInfoList[] | select(.DeviceName == $device) | .StreamName')
echo "Stream Names: $STREAM_NAMES"

# Check if there are multiple stream names and select the first one
STREAM_NAME=$(echo "$STREAM_NAMES" | head -n 1)

# Check if STREAM_NAME is empty
if [[ -z "$STREAM_NAME" ]]; then
  echo "Error: No stream found for the device name $AWS_IOT_CORE_THING_NAME."
  exit 1
fi

# Set the metric name and namespace
METRIC_NAME="PutMedia.Success"
NAMESPACE="AWS/KinesisVideo"
TIME_RANGE=60

# Get the current time
NOW=$(date +%s)

# Calculate the start and end times in the correct ISO 8601 format
START_TIME=$(date -u -d "@$(($NOW - $TIME_RANGE))" +"%Y-%m-%dT%H:%M:%SZ")
END_TIME=$(date -u -d "@$NOW" +"%Y-%m-%dT%H:%M:%SZ")
echo "START TIME IS $START_TIME"
echo "END TIME IS $END_TIME"

# Retrieve the metric data from CloudWatch
RESULT=$(aws cloudwatch get-metric-statistics \
  --namespace "$NAMESPACE" \
  --metric-name "$METRIC_NAME" \
  --dimensions Name=StreamName,Value="$STREAM_NAME" \
  --start-time "$START_TIME" \
  --end-time "$END_TIME" \
  --period "$TIME_RANGE" \
  --statistics Sum \
  --query "Datapoints[0].Sum" \
  --output text)

# Check if RESULT is empty
if [[ -z "$RESULT" || "$RESULT" == "None" ]]; then
  echo "No data points found for the specified metric."
else
  # Display the result
  echo "Result: $RESULT"
fi
