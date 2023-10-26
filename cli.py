import argparse
import filecmp
import os
import shutil
import sqlite3
import sys
from collections import defaultdict

from utils import copytree_with_progress

DATABASE_PATH = os.path.expanduser(
    os.path.join("~", "AppData", "Local", "Amazon Games", "Data", "Games", "Sql", "GameInstallInfo.sqlite")
)

LOCATION_OPTIONS = [
    r"C:\Amazon Games\Library",
    r"D:\Games\AmazonGames",  # Frequently played
    r"E:\Games\AmazonGames",  # Infrequently played
    r"Z:\Games\AmazonGames"  # Won't play
]


def get_games_by_base_dir():
    games_by_base_dir = defaultdict(list)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ProductAsin, ProductTitle, InstallDirectory FROM DbSet")
    game_rows = cursor.fetchall()
    conn.close()

    for game_id, game_name, install_dir in game_rows:
        base_install_dir = os.path.dirname(install_dir)
        game_tuple = (game_id, game_name, install_dir)
        games_by_base_dir[base_install_dir].append(game_tuple)

    for root_location, game_tuple in games_by_base_dir.items():
        game_tuple.sort(key=lambda x: x[1].lower())

    global_game_index = 1
    for root_location, game_tuple in games_by_base_dir.items():
        for index, game in enumerate(game_tuple, start=1):
            game_tuple[index - 1] = (global_game_index,) + game
            global_game_index += 1

    return games_by_base_dir


def list_games(games_by_base_dir):
    print("GAMES BY ROOT INSTALL LOCATION:")
    for root_location, game_tuple in games_by_base_dir.items():
        print(f"\nRoot Install Location: {root_location}")
        for (index, game_id, game_name, install_dir) in game_tuple:
            print(f"  {index}. {game_id} - {game_name}")


def update_manifest(game_id, new_install_game_dir):
    shutil.copyfile(DATABASE_PATH, f'{DATABASE_PATH}.bak')

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE DbSet SET InstallDirectory = ? WHERE ProductAsin = ?",
            (new_install_game_dir, game_id)
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"ERROR: Failed to update GameInstallInfo.sqlite. Exception: {e}")


def move_game(game_id, desired_base_dir):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT InstallDirectory FROM DbSet WHERE ProductAsin = ?",
        (game_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(f"ERROR: Game with ID {game_id} not found.")
        return

    source_install_game_dir = row[0]
    new_install_game_dir = os.path.join(
        desired_base_dir,
        os.path.basename(source_install_game_dir)
    )

    source_install_data_dir = os.path.join(
        os.path.join(os.path.dirname(source_install_game_dir), "__InstallData__"),
        os.path.basename(new_install_game_dir)
    )
    new_install_data_dir = os.path.join(
        os.path.join(os.path.dirname(new_install_game_dir), "__InstallData__"),
        os.path.basename(new_install_game_dir)
    )

    if os.path.abspath(source_install_game_dir) != os.path.abspath(new_install_game_dir):
        print(f"Copying from {source_install_game_dir} to {new_install_game_dir}")
        copytree_with_progress(source_install_game_dir, new_install_game_dir)
        game_dircmp = filecmp.dircmp(source_install_game_dir, new_install_game_dir, ignore=None)

        print(f"Copying from {source_install_data_dir} to {new_install_data_dir}")
        copytree_with_progress(source_install_data_dir, new_install_data_dir)
        data_dircmp = filecmp.dircmp(source_install_data_dir, new_install_data_dir, ignore=None)

        if not game_dircmp.left_only and not game_dircmp.right_only and not data_dircmp.left_only and not data_dircmp.right_only:
            print("\nCopy successful, updating manifest and removing old install location.")
            update_manifest(game_id, new_install_game_dir)
            shutil.rmtree(source_install_game_dir)
            shutil.rmtree(source_install_data_dir)
        else:
            print("\nERROR: File comparison mismatch:")
            print("Game Directories:")
            print("Left only: " if game_dircmp.left_only else "None")
            print("Right only: " if game_dircmp.right_only else "None")

            print("Data Directories:")
            print("Left only: " if data_dircmp.left_only else "None")
            print("Right only: " if data_dircmp.right_only else "None")

            print("\nRemoving new install location.")
            for directory in [new_install_game_dir, new_install_data_dir]:
                if os.path.exists(directory):
                    shutil.rmtree(directory)
    else:
        print("\nPreferred location is the same as the current location. No action required.")


def move_all_games(desired_base_dir, games_by_base_dir):
    for root_location, game_tuple in games_by_base_dir.items():
        for (global_game_index, game_id, game_name, install_dir) in game_tuple:
            move_game(game_id, desired_base_dir)


def interactive(games_by_base_dir):
    list_games(games_by_base_dir)

    selected_index = input("\nEnter the index number of the game you want to update or 'all' to move all games: ")

    if selected_index.lower() == 'all':
        for index, location in enumerate(LOCATION_OPTIONS, start=1):
            print(f"{index}. Option {index}: {location}")

        try:
            desired_option = int(input(f"\nEnter your choice (1-{len(LOCATION_OPTIONS)}): "))
            if 1 <= desired_option <= len(LOCATION_OPTIONS):
                desired_base_dir = LOCATION_OPTIONS[desired_option - 1]
                move_all_games(desired_base_dir, games_by_base_dir)
            else:
                print("ERROR: Invalid choice. Exiting.")
        except ValueError:
            print("ERROR: Invalid input. Please enter a valid choice.")
    else:
        try:
            selected_index = int(selected_index)
            selected_game_id, selected_game_name, selected_install_dir = None, None, None
            for root_location, game_tuple in games_by_base_dir.items():
                for (global_game_index, game_id, game_name, install_dir) in game_tuple:
                    if global_game_index == selected_index:
                        selected_game_id, selected_game_name, selected_install_dir = game_id, game_name, install_dir
                        break

            if selected_game_id:
                print(f"\nSelected Game:")
                print(f"Game ID: {selected_game_id}")
                print(f"Game Name: {selected_game_name}")
                print(f"Current Install Location: {selected_install_dir}")

                print("\nChoose a preferred installation location option:")

                for index, location in enumerate(LOCATION_OPTIONS, start=1):
                    print(f"{index}. Option {index}: {location}")

                try:
                    desired_option = int(input(f"\nEnter your choice (1-{len(LOCATION_OPTIONS)}): "))
                    if 1 <= desired_option <= len(LOCATION_OPTIONS):
                        desired_base_dir = LOCATION_OPTIONS[desired_option - 1]
                        move_game(selected_game_id, desired_base_dir)
                    else:
                        print("ERROR: Invalid choice. Exiting.")
                except ValueError:
                    print("ERROR: Invalid input. Please enter a valid choice.")
            else:
                print("ERROR: Invalid Game ID.")
        except ValueError:
            print("ERROR: Invalid input. Please enter a valid index number or 'all'.")


def main():
    parser = argparse.ArgumentParser(description="Amazon Games Library Manager CLI")
    subparsers = parser.add_subparsers(title="subcommands", dest="command")

    subparsers.add_parser("list", help="List all games currently recognized by Amazon Games.")

    move_parser = subparsers.add_parser("move", help="Move a game to a different location.")
    move_parser.add_argument("game_id", help="Game ID to move.")
    move_parser.add_argument("desired_base_dir", help="Desired base directory.")

    args = parser.parse_args()

    if args.command == "list":
        games_by_base_dir = get_games_by_base_dir()
        list_games(games_by_base_dir)
    elif args.command == "move":
        move_game(args.game_id, args.desired_base_dir)
    else:
        print("No command provided, running in interactive mode.")
        games_by_base_dir = get_games_by_base_dir()
        interactive(games_by_base_dir)


if __name__ == "__main__":
    main()
