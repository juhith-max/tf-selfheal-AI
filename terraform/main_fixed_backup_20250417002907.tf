resource "aws_instance" "example" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"
}

resource "aws_instance" "example_backup" {
  ami           = "ami-90123456"
  instance_type = "t2.micro"
}