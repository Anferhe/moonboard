# This script must be called from moonboard folder
main_dir=`pwd`

sudo apt install -y python3-pip python3-dbus libgirepository1.0-dev
sudo pip3 install -r $main_dir/install/requirements.txt


echo "Install moonboard service"
led_service="moonboard_led.service"
sudo cp $main_dir/led/$led_service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/$led_service
sudo systemctl daemon-reload
sudo systemctl enable $led_service

echo "Install DBUS BLE service"
ble_service="com.moonboard.service"
sudo cp $main_dir/ble/com.moonboard.conf /etc/dbus-1/system.d/
sudo cp $main_dir/ble/$ble_service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/$ble_service
sudo systemctl daemon-reload
sudo systemctl enable $ble_service

echo "Prepare logfiles"
sudo touch /var/log/moonboard
sudo chown pi:pi /var/log/moonboard
sudo chown pi:pi /var/log/moonboard

echo "Restarting in 5 seconds to finalize changes. CTRL+C to cancel"
sleep 1 > /dev/null
printf "."
sleep 1 > /dev/null
printf "."
sleep 1 > /dev/null
printf "."
sleep 1 > /dev/null
printf "."
sleep 1 > /dev/null
printf " Restarting"
sudo reboot
