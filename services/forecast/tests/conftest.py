import os

os.environ["USE_FIXTURES"] = "1"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["SIM_CONTROL_URL"] = "http://localhost:9999"
