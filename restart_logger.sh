#!/bin/bash
echo "Restarting Continuous Sensor Logger..."
sudo systemctl restart sensor_logger.service
echo "Checking Status..."
sudo systemctl status sensor_logger.service --no-pager | grep "Active:"
echo "Done!"
