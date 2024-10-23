# AWS EMEA GenAI Automotive Hackathon - AI-Powered Regulatory Compliance System PoC

## AWS Lambda Configuration
Lambda serves as a simple API endpoint.

### First, prepare the AWS Lambda deployment:
1. git clone <REPO_URL> && cd <REPO_FOLDER>
2. mkdir packages && cd packages
3. python3.12 -m venv .venv
4. source .venv/bin/activate
5. pip3 --ignore-installed -t . -r ../requirements.txt
6. zip -r ../deployment_package.zip .
7. cd ../ && zip -r deployment_package.zip lambda_function.py

### Then, deploy the AWS Lambda with the AWS Console:
1. Navigate to https://console.aws.amazon.com/lambda/home and press `Create Function`
2. Choose the `Author from scratch`, specify whatever name you want, and select `Python 3.12` for the runtime.
   Keep the Architecture `x86_64`.
3. Under `Change default execution role` you need to specify the IAM role with `AdministratorAccess` (or with less permissions if you're sure on the list).
4. Under `Additional Configurations` tick the `Enable function URL` with `Auth type` is `NONE`.
5. Press `Create function`.
6. Open the created function and under the `Code` tab press `Upload from` -> `.zip file` and choose earlier prepared `deployment_package.zip`.
