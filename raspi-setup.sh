if [ "$EUID" -ne 0 ]
  then echo "Please run this script as root."
  exit
fi

echo "Enabling I2C"
raspi-config nonint do_i2c 0

