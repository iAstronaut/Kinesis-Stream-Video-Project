#!/bin/bash
source /opt/axisapp/gateway.bash

# TODO: 以下を変更する
# ストリーム名を指定する
STREAM_NAME=$(aws kinesisvideo list-streams --region "$AWS_DEFAULT_REGION" --debug | jq -r --arg device "$AWS_IOT_CORE_THING_NAME" '.StreamInfoList[] | select(.DeviceName == $device) | .StreamName')

# メトリクス名を指定する
METRIC_NAME="PutMedia.Success"

# 名前空間を指定する
NAMESPACE="AWS/KinesisVideo"

# 時間範囲を指定する (秒単位)
TIME_RANGE=60

# 現在時刻を取得する
NOW=$(date +%s)

# 開始時刻と終了時刻を計算する
START_TIME=$(date -u -d "@$(($NOW - $TIME_RANGE))" +"%Y-%m-%dT%H:%M:%SZ")
END_TIME=$(date -u -d "@$NOW" +"%Y-%m-%dT%H:%M:%SZ")
echo "START TIME IS $START_TIME "
echo "END TIME IS $END_TIME"
# CloudWatch CLI を使用してメトリクスデータを取得する
RESULT=$(aws cloudwatch get-metric-statistics \
  --namespace $NAMESPACE \
  --metric-name $METRIC_NAME \
  --dimensions Name=StreamName,Value=$STREAM_NAME \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --period $TIME_RANGE \
  --statistics Sum \
  --query "Datapoints[0].Sum")

# 結果を表示する
echo "結果: $RESULT"
