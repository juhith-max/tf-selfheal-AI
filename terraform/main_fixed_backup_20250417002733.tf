resource "aws_instance" "example2" {
name = "example-instance"
ami = "ami-12345678"
instance_type = "t2.micro"
}