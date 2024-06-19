#!/bin/bash
sleep_time=1800
# TODO: 以下を変更する GWのID
gw_name="23122102"
To="gwsys_admin_user@axisware.co.jp"
#To="kazumasa.nemoto@axisware.co.jp,masahiro.harada@axisware.co.jp"
#To="taiki.miura@axisware.co.jp"

# Thời gian chờ sau khi khởi động lại
# sleep 60
# Thời gian đo lường lỗi liên kết
loop_time=300
is_reboot=false
# số lần lỗi khi không kết nối camera mới coi là không kết nối
max_failed_cnt=3
kvs_failed_cnt=0
# số lần thực thi get_fragment_list.py liên tiếp
exec_max_cnt=3
exec_cnt=0
# thời gian đợi sau khi khởi động lại gateway
gateway_restart_time=80
nw_retry_time=30

start_time=`date +%s`

function gateway_restart () {

   echo "gateway_restart"
   is_connected
   result=$?

   if [ $result = 0 ]; then
       return
   else
      echo "gateway.service dừng"
      sudo systemctl stop gateway.service
      sleep 5
      sudo systemctl kill gateway.service
      # netstat để rtsp bị đóng sau khoảng 60 giây nên chờ đợi 70 giây trước khi start
      sleep 70 
      echo "gateway.service bắt đầu"
      sudo systemctl start gateway.service
      sleep $gateway_restart_time
      return
   fi
}

function is_connected(){
   result=$(/opt/gateway/install/putmedia_check.sh)
   echo "isconect"
   echo $result
   if [ "$result" = "null" ]; then
	   echo "con1"
           return 1
   else
       result=${result%.*}
       if [ $result -gt 0 ]; then
           return 0
       else
	       echo "con1"
           return 1
       fi
   fi
}



while true
do
        # lấy thời gian hiện tại
        now=`date +%s`
        diff=$((now - start_time))
        
        # sau khi đo lường lỗi liên kết một khoảng thời gian, bắt đầu đo lường lại
        #if [[ $diff -gt $loop_time ]]; thenif 
        if [[ $exec_max_cnt = $exec_cnt ]]; then
                start_time=`date +%s`
                kvs_failed_cnt=0
                exec_cnt=0
		is_reboot=false
                sleep $loop_time
        fi

        # kiểm tra lỗi liên kết với kinesis video stream
        #is_connected=$(sudo python3 /opt/gateway/install/get_fragment_list.py)
        is_connected
	result=$?

        exec_cnt=$((exec_cnt + 1))
        if [ $result = 1 ]; then
            echo "Số lần không kết nối liên tục"
            kvs_failed_cnt=$((kvs_failed_cnt + 1))
	else 
            echo "Kết nối OK"
        fi

        # sau khi đạt đến số lần lỗi cố định, khởi động lại
        if [ $kvs_failed_cnt -eq $max_failed_cnt]
            exec_cnt=0
            is_reboot=true
        fi

        # trước khi khởi động lại, gửi email thông báo
        if $is_reboot; then
		is_reboot=false
        echo "Reconnect......."
	is_reboot=false
    status=$(systemctl status NetworkManager | grep -i "active")

    if echo "$status" | grep -q "active"; then
        result1=0
    else
        result1=1
    fi
        if [result1=1]; then
        sudo systemctl restart NetworkManager
        sleep $nw_retry_time
        gateway_restart
        is_connected
        fi
        else
        gateway_restart
        is_connected
	result=$?
         if [ $result = 1 ]; then
               echo "Kết nối mạng lại..."
               sudo nmcli device disconnect wlan0
               sudo nmcli device connect wlan0
               sleep $nw_retry_time
               is_connected
               result=$?   
               if [ $result = 1 ]; then
                    sleep 10
                    echo "Không thể kích hoạt kết nối mạng."
                    echo "Bộ điều khiển USB đang tắt..."
                    echo "1-1" | sudo tee /sys/bus/usb/drivers/usb/unbind
                    echo "Xong."
                    echo " nghỉ 5 giây..."  sleep 5s
                    echo "Bộ điều khiển USB đang khởi động lại..."
                    echo "1-1" | sudo tee /sys/bus/usb/drivers/usb/bind
                    echo "Xong. Kiểm tra lại"
                    sleep 10
                    sudo nmcli device connect wlan0
                    sleep $nw_retry_time
                    gateway_restart
                    is_connected
                    result=$? 
                    if [ $result = 1 ]; then
                       sudo shutdown -r now
                        if [ $? -eq 0 ]; then
                          break
                        fi
                    fi 
               fi
            fi
        fi
	sleep 10
done

