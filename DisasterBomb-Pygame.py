# Project: Incident Bomb Game
# for AWS Game Builder Challenge
# created by Andy Nguyen 

import pygame # must install using command "pip install pygame"
import random
import time
import uuid
import json
import boto3 # must install using command "pip install boto3"
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime
from decimal import Decimal

# initialise the S3 client
s3 = boto3.client('s3')
bucket_name = 'disaster-bomb-game-bucket'

# function to upload game asset to Amazon S3
def upload_game_asset_to_s3(player_id, score, chosen_set, num_passed, status):
    try:
        game_id = str(uuid.uuid4())
        current_best = get_best_score(player_id)
        current_score = get_player_score(player_id)
        # convert all values to Decimal type for consistent calculation
        score = Decimal(str(score))
        current_best = Decimal(str(current_best))
        current_score = Decimal(str(current_score))
        # calculate new cumulative score
        new_cumulative_score = Decimal('0') if status != 'Win' else current_score + score
        # calculate new best score (compare current_best with current_score + new score)
        best_score = max(current_best, current_score + score)
        # print debug statements to the console.
        print(f"S3 Debug values:")
        print(f"Current best: {current_best}")
        print(f"Current score: {current_score}")
        print(f"Game score: {score}")
        print(f"New cumulative score: {new_cumulative_score}")
        print(f"New best score: {best_score}")
        game_data = {
            "PlayerID": player_id,
            "GameID": game_id,
            "Chosen_Scenario_Set": chosen_set,
            "Cumulative_Score": float(new_cumulative_score),
            "Best_Score": float(best_score),
            "Game_Score": float(score),
            "Num_Passed_Scenarios": num_passed,
            "Status": status,
            "Timestamp": datetime.now().isoformat()
        }
        # custom JSON encoder to handle Decimal types
        class DecimalEncoder(json.JSONEncoder):
            def default(self, obj):
                from decimal import Decimal
                if isinstance(obj, Decimal):
                    return float(obj)
                return super(DecimalEncoder, self).default(obj)
        json_data = json.dumps(game_data, indent=2, cls=DecimalEncoder)
        file_name = f"game_data/{player_id}/{game_id}.json"
        # upload to S3
        s3.put_object(
            Bucket=bucket_name,
            Key=file_name,
            Body=json_data,
            ContentType='application/json'
        )
        print(f"Game data has been uploaded to S3 for player {player_id} with game ID {game_id}")
    except NoCredentialsError:
        print("No valid AWS credentials found. Please configure them.")
    except Exception as e:
        print(f"Error occurs when uploading game data to S3: {e}")


# function to create an Amazon DynamoDB table if it does not exist yet.
def create_dynamodb_table_if_not_exists():
    try:
        existing_tables = dynamodb.meta.client.list_tables()['TableNames']
        
        if 'Disaster-Bomb-Game-Database' not in existing_tables:
            print("Creating DynamoDB table...")
            table = dynamodb.create_table(
                TableName='Disaster-Bomb-Game-Database',
                KeySchema=[
                    {
                        'AttributeName': 'PlayerID',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'GameID',
                        'KeyType': 'RANGE'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'PlayerID',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'GameID',
                        'AttributeType': 'S'
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            
            # wait until the table exists
            table.meta.client.get_waiter('table_exists').wait(
                TableName='Disaster-Bomb-Game-Database'
            )
            print("Table created successfully!")
            return table
        else:
            print("Table already exists")
            return dynamodb.Table('Disaster-Bomb-Game-Database')
    except Exception as e:
        print(f"Error creating or checking table: {e}")
        return None
    
# initialise the DynamoDB database for the game
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = create_dynamodb_table_if_not_exists()

if table is None:
    print("Failed to initialize DynamoDB table. Please check your AWS credentials and permissions.")
    # handle the error appropriately - maybe exit the game or fall back to local storage

# function to get player's current score
def get_player_score(player_id):
    try:
        response = table.query(
            KeyConditionExpression='PlayerID = :pid',
            ExpressionAttributeValues={
                ':pid': player_id
            },
            Limit=1,
            ScanIndexForward=False
        )
        
        items = response.get('Items', [])
        if items:
            last_game_status = items[0].get('Status')
            if last_game_status != 'Win':
                return 0  # Reset to 0 if the last game was lost
            return items[0].get('Cumulative_Score', 0)
        return 0
    except Exception as e:
        print(f"Error getting player score: {e}")
        return 0
    
# function to get player's best cumulative score if they have played before
def get_best_score(player_id):
    try:
        # use a strongly consistent read and sort by timestamp in descending order
        response = table.query(
            KeyConditionExpression='PlayerID = :pid',
            ExpressionAttributeValues={
                ':pid': player_id
            },
            ProjectionExpression='Best_Score',
            ScanIndexForward=False,  # Get most recent first
            ConsistentRead=True,
            Limit=1
        )
        items = response.get('Items', [])
        if items:
            best_score = Decimal(str(items[0].get('Best_Score', 0)))
            print(f"Retrieved best score for player {player_id}: {best_score}")
            return best_score
        return Decimal('0')
    except Exception as e:
        print(f"Error getting best score: {e}")
        return Decimal('0')

# function to store game data in Amazon DynamoDB
def store_game_data_in_database(player_id, score, scenario_set, num_passed_scenarios, status):
    try:
        game_id = str(uuid.uuid4())
        current_best = get_best_score(player_id)
        current_score = get_player_score(player_id)
        score = Decimal(str(score))
        # convert all values to Decimal for consistent comparison
        current_best = Decimal(str(current_best))
        current_score = Decimal(str(current_score))
        # calculate new cumulative score
        new_cumulative_score = Decimal('0') if status != 'Win' else current_score + score
        # calculate new best score
        best_score = max(current_best, current_score + score)
        # print debug statements to the console
        print(f"Debug values:")
        print(f"Current best: {current_best}")
        print(f"Current score: {current_score}")
        print(f"Game score: {score}")
        print(f"New cumulative score: {new_cumulative_score}")
        print(f"New best score: {best_score}")
        # first, try to update with a condition
        try:
            table.put_item(
                Item={
                    'PlayerID': player_id,
                    'GameID': game_id,
                    'Chosen_Scenario_Set': scenario_set,
                    'Cumulative_Score': new_cumulative_score,
                    'Best_Score': best_score,
                    'Game_Score': score,
                    'Num_Passed_Scenarios': num_passed_scenarios,
                    'Status': status,
                    'Timestamp': datetime.now().isoformat()
                },
                ConditionExpression='attribute_not_exists(GameID)'
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                print("Retrying update due to condition check failure...")
                # if condition fails, try update with a new GameID
                game_id = str(uuid.uuid4())
                table.put_item(
                    Item={
                        'PlayerID': player_id,
                        'GameID': game_id,
                        'Chosen_Scenario_Set': scenario_set,
                        'Cumulative_Score': new_cumulative_score,
                        'Best_Score': best_score,
                        'Game_Score': score,
                        'Num_Passed_Scenarios': num_passed_scenarios,
                        'Status': status,
                        'Timestamp': datetime.now().isoformat()
                    }
                )
        # verify the update with multiple retries
        max_retries = 3
        retry_count = 0
        verified = False
        while retry_count < max_retries and not verified:
            time.sleep(0.5 * (retry_count + 1))  # exponential backoff
            verified_best = get_best_score(player_id)
            if verified_best == best_score:
                verified = True
                print(f"Best score verified successfully: {verified_best}")
                break
            else:
                print(f"Verification attempt {retry_count + 1}: Expected {best_score}, got {verified_best}")
                # try to update using update_item with conditional expression
                try:
                    table.update_item(
                        Key={
                            'PlayerID': player_id,
                            'GameID': game_id
                        },
                        UpdateExpression='SET Best_Score = :new_best',
                        ConditionExpression='attribute_not_exists(Best_Score) OR Best_Score < :new_best',
                        ExpressionAttributeValues={
                            ':new_best': best_score
                        }
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                        print(f"Error updating best score: {e}")
            retry_count += 1
        if not verified:
            print(f"Warning: Could not verify best score update after {max_retries} attempts")
            # one final attempt using atomic update
            try:
                table.update_item(
                    Key={
                        'PlayerID': player_id,
                        'GameID': game_id
                    },
                    UpdateExpression='SET Best_Score = :new_best',
                    ConditionExpression='attribute_not_exists(Best_Score) OR Best_Score < :new_best',
                    ExpressionAttributeValues={
                        ':new_best': best_score
                    },
                    ReturnValues='UPDATED_NEW'
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    print(f"Final atomic update failed: {e}")
        print(f"Game data stored successfully for player {player_id} in Amazon DynamoDB.")    
        return best_score
    except Exception as e:
        print(f"Error occurs when storing game data in Amazon DynamoDB: {e}")
        return current_best

# read scenarios stored in the separate text file
def read_scenario(filename):
    try:
        with open(filename, 'r') as file:
            return file.readlines()
    except FileNotFoundError:
        print("File not found.")
        return []
    

# pygame setup
pygame.init()
if not pygame.display.get_init():
    print("We're sorry! Pygame is not initialized. Please try again later!")
# screen settings
WIDTH, HEIGHT = 1500, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Disaster Bomb Game")
# colours
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)
VIOLET = (143, 0, 255)
BLUE = (0, 0, 255)
ORANGE = (255, 165, 0)
DARK_RED = (139, 0, 0)
DARK_GREEN = (2, 48, 32)
AQUA = (51, 255, 255)
# fonts
font = pygame.font.Font(None, 24)
# images/visuals
bad_end_world_img = pygame.image.load("bad_end_world.jpg").convert()
destroyed_world_img = pygame.image.load("destroyed_world.jpg").convert()
happy_city_img = pygame.image.load("happy_futuristic_city.jpg").convert()

# game loop and logic
def PlayIncidentBombGame(player_id, scenario_set):
    score = 0
    # at the start of the game, get the player's existing score
    current_total_score = get_player_score(player_id)
    num_passed_scenarios = 0
    if scenario_set == 10:
        num_helps = 3 # for set 10, player is allowed 3 helps of cutting the correct string and still get full 10 points for each help.
    elif scenario_set == 15:
        num_helps = 5 # for set 15, player is allowed 5 helps of cutting the correct string and still get full 10 points for each help.
    elif scenario_set == 20:
        num_helps = 6 # for set 20, player is allowed 6 helps of cutting the correct string and still get full 10 points for each help.
    scenarios = read_scenario('incidentscenarios.txt')
    # define string options per set
    all_string_options = {
        10: ["red", "green"],
        15: ["red", "green", "yellow"],
        20: ["red", "green", "yellow", "violet"]
    }
    answers = all_string_options[scenario_set]
    # button configuration
    button_config = {
        "red": {"color": RED, "pos": (150, 400)},
        "green": {"color": GREEN, "pos": (325, 400)},
        "yellow": {"color": YELLOW, "pos": (500, 400)},
        "violet": {"color": VIOLET, "pos": (675, 400)},
        "help": {"color": ORANGE, "pos": (850, 400)}  # changed color to ORANGE for better visibility
    }

    for i in range(scenario_set):
        scenario = random.choice(scenarios).strip()
        correct_string = random.choice(answers)
        timer = 30
        selected = None
        running = True
        while running:
            screen.fill(PURPLE)
            # display the scenario
            scenario_text = font.render(f"Scenario {i+1}: {scenario}", True, WHITE)
            screen.blit(scenario_text, (20, 20))
            # draw buttons dynamically
            buttons = {}
            # draw colour string buttons
            for answer in answers:
                button_rect = pygame.draw.ellipse(
                    screen,
                    button_config[answer]["color"],
                    (*button_config[answer]["pos"], 150, 50)
                )
                buttons[answer] = button_rect
                # add text to buttons
                button_text = font.render(answer.capitalize(), True, BLACK)
                screen.blit(
                    button_text,
                    (button_rect.centerx - button_text.get_width() // 2,
                    button_rect.centery - button_text.get_height() // 2)
                )
            
            # draw help button separately
            help_button_rect = pygame.draw.ellipse(
                screen,
                button_config["help"]["color"],
                (*button_config["help"]["pos"], 150, 50)
            )
            buttons["help"] = help_button_rect
            help_text = font.render("Help", True, BLACK)
            screen.blit(
                help_text,
                (help_button_rect.centerx - help_text.get_width() // 2,
                help_button_rect.centery - help_text.get_height() // 2)
            )
            # display timer
            timer_text = font.render(f"Time remaining: {timer}s", True, WHITE)
            screen.blit(timer_text, (20, 100))
            # display current game score, cumulative score, and best score
            score_text = font.render(f"Game Score: {score} | Current Total: {current_total_score} | Best Score: {get_best_score(player_id)}", True, WHITE)
            screen.blit(score_text, (20, 140))
            # display number of helps
            help_counter_text = font.render(f"Helps remaining: {num_helps}", True, WHITE)
            screen.blit(help_counter_text, (20, 60))  # position it below the scenario text
            # display player ID
            player_id_text = font.render(f"Player ID: {player_id}", True, WHITE)
            screen.blit(player_id_text, (20, 40))
            # event handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    for answer, rect in buttons.items():
                        if rect.collidepoint(event.pos):
                            selected = answer
            if selected:
                # when updating the score during gameplay
                if selected == correct_string:
                    score += 10
                    num_passed_scenarios += 1
                    current_total_score += 10
                    result_text = font.render(f"Success! Bomb disarmed. Total Score: {current_total_score}", True, GREEN)
                elif selected == "help":  # help button logic
                    if num_helps > 0:
                        score += 10
                        current_total_score += 10
                        num_passed_scenarios += 1
                        num_helps -= 1
                        result_text = font.render(f"Help used! The correct fuse to cut is {correct_string}. Helps remaining: {num_helps}", True, ORANGE)
                        if num_helps == 0:
                            help_msg_text = font.render("No more helps available!", True, RED)
                            screen.blit(help_msg_text, (20, 180))
                    else:
                        result_text = font.render("No helps remaining! You must choose a string.", True, RED)
                        selected = None  # allow player to make another choice
                        pygame.display.flip()
                        continue
                else:
                    result_text = font.render(f"Failed! Bomb exploded. The correct fuse was {correct_string}.", True, RED)
                screen.blit(result_text, (20, 200))
                pygame.display.flip()
                pygame.time.delay(2000)
                running = False
            # update screen and decrement timer
            pygame.display.flip()
            pygame.time.delay(1000)
            timer -= 1
            if timer <= 0:
                result_text = font.render("Time's up! Bomb exploded.", True, RED)
                screen.blit(result_text, (20, 200))
                pygame.display.flip()
                pygame.time.delay(2000)
                running = False
    # display final result
    pass_criteria = {10: 6, 15: 9, 20: 12}
    # at the end where you show the final screen:
    if score >= pass_criteria[scenario_set] * 10:  
        status = "Win"
        new_best_score = store_game_data_in_database(player_id, score, scenario_set, num_passed_scenarios, status)
        current_total_score = get_player_score(player_id)
        screen.blit(happy_city_img, (0, 0))
        final_text = font.render(f"Game Clear: Agent {player_id}, you have won the game and restore the happiness of this world! Game Score: {score} | Current Total: {current_total_score} | Best Score: {new_best_score}", True, WHITE)
    else:
        status = "Lose"
        new_best_score = store_game_data_in_database(player_id, score, scenario_set, num_passed_scenarios, status)
        current_total_score = get_player_score(player_id)
        screen.blit(destroyed_world_img, (0, 0))
        final_text = font.render(f"Game Over: Agent {player_id}, you failed to save the world! Game Score: {score} | Current Total: {current_total_score} | Best Score: {new_best_score}", True, RED)

    # Update the display with new scores
    screen.blit(final_text, (200, 200))
    pygame.display.flip()
    # Wait for a moment to show the final screen
    pygame.time.wait(2000)  # Wait for 2 seconds
    # When transitioning to a new set or replaying, make sure to get the latest scores
    current_total_score = get_player_score(player_id)
    best_score = get_best_score(player_id)
    # display the replay button after finishing the game.
    replay_button = pygame.draw.rect(screen, GREEN, (300, 300, 200, 50))
    replay_text = font.render("Replay", True, BLACK)
    screen.blit(replay_text, (replay_button.centerx - replay_text.get_width() // 2, 
                              replay_button.centery - replay_text.get_height() // 2))
    pygame.display.flip()
    # wait for player action
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if replay_button.collidepoint(event.pos):
                    main()
                    waiting = False

def main():
    print("Open Pygame window...")
    time.sleep(0.5)
    def display_message(messages, delay=1000):
        screen.blit(bad_end_world_img, (0, 0))
        y_offset = 20
        for message in messages:
            text_surface = font.render(message, True, BLACK)
            screen.blit(text_surface, (20, y_offset))
            y_offset += 40
        pygame.display.flip()
        pygame.time.delay(delay)

    # prompt the user to enter their player ID
    player_id = ""
    typing = True
    input_box = pygame.Rect(20, 200, 400, 50)
    input_text = ""

    # display welcome messages
    welcome_messages = [
        "Welcome to the Disaster Bomb Game!",
        "You are an agent in the Bad End World.",
        "A series of predicted disasters will happen.",
        "Your task is to cut a string to disarm the bomb that predicts the disaster.",
        "You have 30 seconds to cut the string to prevent each disaster",
        "Click on the correct button to cut that string.",
        "If you fail, the bomb will explode, and you will fail a disaster scenario.",
        "Choose one of three difficulty levels: a set of 10, 15, and 20 scenarios:",
        "- For set of 10 (easy level): Choose to cut one of the two strings and pass at least 6 scenarios to win the game.",
        "- For set of 15 (medium level): Choose to cut one of the three strings and pass at least 9 scenarios to win the game.",
        "- For set of 20 (difficult level): Choose to cut one of the four strings and pass at least 12 scenarios to win the game.",
        "Please reuse your player ID everytime you play the game so your cumulative and best scores can be saved.",
        "Good luck, Agent!",
        "@2024 Disaster Bomb Game"
    ]
    display_message(welcome_messages, delay=5000)
    # display input prompt.
    while typing:
        screen.blit(bad_end_world_img, (0, 0))
        instruction_text = font.render("Enter your player ID below:", True, WHITE)
        screen.blit(instruction_text, (20, 150))

        pygame.draw.rect(screen, BLACK, input_box, 2)
        input_surface = font.render(input_text, True, BLACK)
        screen.blit(input_surface, (input_box.x + 10, input_box.y + 10))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    player_id = input_text.strip()
                    typing = False
                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                else:
                    input_text += event.unicode
        pygame.display.flip()
    # confirm player ID and continue.
    ready_messages = [
        f"Player ID: {player_id}",
        f"Welcome, Agent {player_id}!"
    ]
    display_message(ready_messages)
    # ready confirmation
    ready = False
    while not ready:
        screen.fill(BLACK)
        ready_text = font.render("Are you ready to save the world?", True, WHITE)
        # display YES and NO buttons for player to choose.
        yes_button = pygame.draw.ellipse(screen, GREEN, (150, 400, 150, 50))
        no_button = pygame.draw.ellipse(screen, RED, (400, 400, 150, 50))
        # add text to YES and NO buttons
        yes_text = font.render("YES", True, BLACK)
        no_text = font.render("NO", True, WHITE)
        # centre text on the buttons
        screen.blit(ready_text, (50, 200))
        screen.blit(yes_text, (yes_button.centerx - yes_text.get_width() // 2, yes_button.centery - yes_text.get_height() // 2))
        screen.blit(no_text, (no_button.centerx - no_text.get_width() // 2, no_button.centery - no_text.get_height() // 2))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if yes_button.collidepoint(event.pos):
                    ready = True
                elif no_button.collidepoint(event.pos):
                    pygame.quit()
                    exit()
        pygame.display.flip()
    # select scenario set/game level to play
    set_choice = 0
    choosing_set = True
    while choosing_set:
        screen.fill(BLACK)
        # display level selection options
        choose_text = font.render("Choose your scenario set:", True, WHITE)
        set10_button = pygame.draw.ellipse(screen, ORANGE, (150, 400, 150, 50))
        set15_button = pygame.draw.ellipse(screen, DARK_RED, (400, 400, 150, 50))
        set20_button = pygame.draw.ellipse(screen, DARK_RED, (650, 400, 150, 50))
        # add text to buttons
        set10_text = font.render("Set 10 (Easy)", True, WHITE)
        set15_text = font.render("Set 15 (Medium)", True, WHITE)
        set20_text = font.render("Set 20 (Difficult)", True, WHITE)
        # centre text on the buttons
        screen.blit(choose_text, (50, 200))
        screen.blit(set10_text, (set10_button.centerx - set10_text.get_width() // 2, set10_button.centery - set10_text.get_height() // 2))
        screen.blit(set15_text, (set15_button.centerx - set15_text.get_width() // 2, set15_button.centery - set15_text.get_height() // 2))
        screen.blit(set20_text, (set20_button.centerx - set20_text.get_width() // 2, set20_button.centery - set20_text.get_height() // 2))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if set10_button.collidepoint(event.pos):
                    set_choice = 10
                    choosing_set = False
                elif set15_button.collidepoint(event.pos):
                    set_choice = 15
                    choosing_set = False
                elif set20_button.collidepoint(event.pos):
                    set_choice = 20
                    choosing_set = False
        pygame.display.flip()
    # Start the game
    display_message(["Let's start the game! Pygame is initialized..."], delay=2000)
    PlayIncidentBombGame(player_id, set_choice)

if __name__ == "__main__":
    main()