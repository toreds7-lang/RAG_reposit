def main():
    number = get_user_input()
    multiplication_table = generate_multiplication_table(number)
    display_table(multiplication_table)

def get_user_input():
    while True:
        user_input = input("Enter a number for the multiplication table: ")
        try:
            number = int(user_input)
            return number
        except ValueError:
            print("Invalid input. Please enter an integer.")

def generate_multiplication_table(number):
    table = []
    for i in range(1, 10):
        product = number * i
        table.append(f"{number} x {i} = {product}")
    return table

def display_table(table):
    for line in table:
        print(line)

# Run the program
if __name__ == "__main__":
    main()