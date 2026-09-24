###############################################################################
# NetTwin 3.0 — VPC Traffic West (us-west-2)
#
# Dedicated adversary & traffic generation environment:
# - Single public subnet with Internet Gateway
# - Houses traffic-gen EC2 instance driving traffic across public internet
###############################################################################

resource "aws_vpc" "traffic_west" {
  provider             = aws.west
  cidr_block           = "10.1.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "vpc-traffic-west"
    Environment = "traffic-west"
    Role        = "traffic-generator-lab"
  }
}

resource "aws_internet_gateway" "igw_west" {
  provider = aws.west
  vpc_id   = aws_vpc.traffic_west.id

  tags = {
    Name = "igw-traffic-west"
  }
}

resource "aws_subnet" "public_west" {
  provider                = aws.west
  vpc_id                  = aws_vpc.traffic_west.id
  cidr_block              = "10.1.1.0/24"
  availability_zone       = "${var.west_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "subnet-public-west-1a"
    Tier = "traffic-generator-public"
  }
}

resource "aws_route_table" "public_west" {
  provider = aws.west
  vpc_id   = aws_vpc.traffic_west.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw_west.id
  }

  tags = {
    Name = "rt-public-traffic-west"
  }
}

resource "aws_route_table_association" "public_west_assoc" {
  provider       = aws.west
  subnet_id      = aws_subnet.public_west.id
  route_table_id = aws_route_table.public_west.id
}
