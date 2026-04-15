import mlflow

# 1. Point MLflow to your local server
mlflow.set_tracking_uri("http://127.0.0.1:5000")

# 2. Create or set an experiment
mlflow.set_experiment("Local_Tracking_Demo")

# 3. Start a run and log data
with mlflow.start_run():
    # Log parameters (configuration)
    mlflow.log_param("epochs", 10)
    mlflow.log_param("learning_rate", 0.001)
    
    # Log metrics (results)
    mlflow.log_metric("loss", 0.45)
    mlflow.log_metric("accuracy", 0.89)
    
    print("Successfully logged data to the local tracking server!")