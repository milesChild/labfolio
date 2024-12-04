# check if the AWS_ACCOUNT_ID environment variable is set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "AWS_ACCOUNT_ID is not set"
    exit 1
fi

# the name of the image should be given as a command line argument
IMAGE_NAME=$1

# the name of the repository should be given as a command line argument
REPOSITORY_NAME=$2

# build the image locally. we must use linux/amd64 to ensure compatibility with Lambda
docker buildx build --platform linux/amd64 -t $IMAGE_NAME .

# login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# tag the image
docker tag $IMAGE_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$REPOSITORY_NAME:latest

# push the image to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$REPOSITORY_NAME:latest