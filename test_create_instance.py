
from model.Request import Request
from datetime import datetime
import tripdata_gen as gen
import config
import os
import sys
import pandas as pd

# Adding project folder
root = os.getcwd().replace("\\", "/")
sys.path.append(root)

# Config is in root


print("Folder instances:", config.root_static_instances_experiments)

if __name__ == "__main__":

    if not os.path.exists(config.root_static_instances_experiments):
        os.makedirs(config.root_static_instances_experiments)

    # Share of each class in customer base
    user_segmentation_dict = {
        "BB": {
            "A": 0.16,
            "B": 0.68,
            "C": 0.16
        },
        "CC": {
            "A": 0.16,
            "B": 0.16,
            "C": 0.68
        },
        "AA": {
            "A": 0.68,
            "B": 0.16,
            "C": 0.16
        },
        # "A": {
        #     "A": 1.00,
        #     "B": 0.00,
        #     "C": 0.00
        # },
        # "C": {
        #     "A": 0.00,
        #     "B": 0.00,
        #     "C": 1.00
        # },
        # "B": {
        #     "A": 0.00,
        #     "B": 1.00,
        #     "C": 0.00
        # }
    }

    tripdata_csv_path = f"{config.root_tripdata}/random_clone_tripdata_excerpt_2011-02-01_000000_2011-02-02_000000_ids.csv"
    

    gen.create_instances_exact_sol(
        config.graph_name,
        [10, 15, 20, 25],
        user_segmentation_dict,
        tripdata_csv_path,
        config.root_static_instances_experiments,
        repeat=10,
        uniform_passenger_count=1
    )

    # ******************************************************************
    # ******************************************************************
    # Reading instances created ****************************************
    # ******************************************************************
    # ******************************************************************

    print("# Reading instances created...")
    # Example of file name: 'city__010__BB__A-16_B-68_C-16.csv'
    folder = config.root_static_instances_experiments
    for file in os.listdir(folder):

        print(f" - \"{file}\"")

        # Removing extension
        base_name = file[:-4]
        # Get instance info from file path
        area, demand_size, user_base_label, class_freq, id_instance, passenger_count = base_name.split(
            "__")
        class_freq_pairs = [
            tuple(pair.split('-'))
            for pair in class_freq.split("_")
        ]

        print(area, demand_size, user_base_label,
              class_freq_pairs, id_instance, passenger_count)
        file_path = "{}/{}".format(folder, file)
        df = pd.read_csv(
            file_path,
            parse_dates=True,
            index_col="pickup_datetime"
        )

        service_level = {
            "A": {
                "pk_delay": 180,
                "trip_delay": 180,
                "sharing_preference": 0
            },
            "B": {
                "pk_delay": 300,
                "trip_delay": 600,
                "sharing_preference": 1
            },
            "C": {
                "pk_delay": 600,
                "trip_delay": 900,
                "sharing_preference": 1
            }
        }

        requests = Request.df_to_request_list(df, service_level)

        for r in requests:  
            print(r.get_info())
