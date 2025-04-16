resource "aws_instance" "example" {
  ami           = "ami-0c321bb676b4d992c"
  instance_type = "t2.micro"
}