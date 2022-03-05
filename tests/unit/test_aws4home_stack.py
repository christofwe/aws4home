import aws_cdk as core
import aws_cdk.assertions as assertions

from aws4home.aws4home_stack import Aws4HomeStack

# example tests. To run these tests, uncomment this file along with the example
# resource in aws4home/aws4home_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = Aws4HomeStack(app, "aws4home")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
