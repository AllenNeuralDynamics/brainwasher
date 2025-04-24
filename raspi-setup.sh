# Check if we are root.
if [ "$EUID" -ne 0 ];
then
    echo "Please run this script as root."
    exit
fi

echo "Enabling I2C"
raspi-config nonint do_i2c 0

#if ! command -v uv 2>&1 >/dev/null
#then
#    echo "uv could not be found. Installing uv."
#    curl -LsSf https://astral.sh/uv/install.sh | sh
#fi


# TODO: launch with systemd.
