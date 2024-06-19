#!/bin/bash

# Thiết bị mạng
network_device="wlan0"

# Địa chỉ NTP
host="ntp.jst.mfeed.ad.jp"

# Số lần thử tối đa
max_retries=10
retry_count=0

# Hàm thực hiện traceroute
perform_traceroute() {
    traceroute $host
    return $?
}

# Hàm kiểm tra trạng thái mạng và kết nối lại nếu cần thiết
check_and_reconnect_network() {
    nmcli device | grep $network_device | grep -q "disconnected"
    if [ $? -eq 0 ]; then
        echo "Thiết bị mạng đã ngắt kết nối, đang kết nối lại..."
        nmcli device disconnect $network_device
        nmcli device connect $network_device
        sleep 30
        systemctl status NetworkManager
    else
        echo "Thiết bị mạng đã được kết nối"
    fi
}

# Hàm bật tắt cung cấp nguồn USB
toggle_usb_power() {
    echo "Tắt cung cấp nguồn USB"
    echo "1-1" | sudo tee /sys/bus/usb/drivers/usb/unbind
    sleep 30
    echo "Bật cung cấp nguồn USB"
    echo "1-1" | sudo tee /sys/bus/usb/drivers/usb/bind
    sleep 60
}

# Logic chính của script
while [ $retry_count -lt $max_retries ]; do
    echo "Đang thử traceroute... (thử $((retry_count + 1)))"
    perform_traceroute
    result=$?

    if [ $result -ne 0 ]; then
        echo "Không thể kết nối đến host, kiểm tra trạng thái mạng..."
        check_and_reconnect_network

        echo "Đang thử traceroute lại..."
        perform_traceroute
        result=$?

        if [ $result -ne 0 ]; then
            echo "Không thể kết nối đến máy chủ NTP, bật cung cấp nguồn USB..."
            toggle_usb_power

            echo "Đang thử traceroute lại..."
            perform_traceroute
            result=$?

            if [ $result -ne 0 ]; then
                echo "Không thể kết nối đến máy chủ NTP, đang thử lại..."
                retry_count=$((retry_count + 1))
                sleep 30
            else
                echo "Đã kết nối đến máy chủ NTP, bắt đầu dịch vụ gateway..."
                sudo systemctl start gateway.service
                break
            fi
        else
            echo "Đã kết nối đến máy chủ truy cập, kiểm tra máy chủ NTP..."
            sleep 30
            perform_traceroute
            result=$?

            if [ $result -eq 0 ]; then
                echo "Đã kết nối đến máy chủ NTP, bắt đầu dịch vụ gateway..."
                sudo systemctl start gateway.service
                break
            else
                retry_count=$((retry_count + 1))
            fi
        fi
    else
        echo "Đã kết nối thành công đến host"
        break
    fi
done

if [ $retry_count -ge $max_retries ]; then
    echo "Traceroute thất bại sau $max_retries lần thử, đang khởi động lại hệ thống..."
    sudo shutdown -r now
fi

