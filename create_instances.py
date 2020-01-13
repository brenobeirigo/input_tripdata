
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

# TRIP DATA
# Columns
#  - pickup_datetime,
#  - passenger_count,
#  - pk_id, dp_id,
#  - pickup_latitude, pickup_longitude,
#  - dropoff_latitude, dropoff_longitude

tripdata_filename = "tripdata_excerpt_2011-2-1_2011-2-28_ids.csv"
tripdata_csv_path = f"{config.root_tripdata}/{tripdata_filename}"

print("Folder instances:", config.root_static_instances_experiments)
print("Trip data file:", tripdata_filename)


# FOLDERS

# Where data is saved
root_static_instances_experiments = config.root_static_instances + "/experiments2"

# Label of the area
area_tripdata = config.graph_name

# INSTANCES CONFIGURATION

# Service levels per class
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

# How many requests will be pulled?
demand_sizes = [5, 20]

# HOW MANY TEST CASES PER INSTANCE?
repeat = 5

# SHOULD PASSENGER COUNT BE UNIFORM?
uniform_passenger_count = 1

if __name__ == "__main__":

    if not os.path.exists(root_static_instances_experiments):
        os.makedirs(root_static_instances_experiments)

    # ******************************************************************
    # Create all instances *********************************************
    # ******************************************************************

    gen.create_instances_exact_sol(
        area_tripdata,
        demand_sizes,
        user_segmentation_dict,
        tripdata_csv_path,
        root_static_instances_experiments,
        repeat=repeat,
        uniform_passenger_count=uniform_passenger_count
    )

    # ******************************************************************
    # Reading instances created ****************************************
    # ******************************************************************

    print("### Reading instances created...")

    # Example of file name: 'city__010__BB__A-16_B-68_C-16.csv'
    folder = config.root_static_instances_experiments
    for file in os.listdir(folder):

        print(f" - \"{file}\"")

        # Removing extension
        base_name = file[:-4]

        # Get instance info from file path
        (area, demand_size, user_base_label, class_freq, id_instance, passenger_count) = base_name.split(
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

        requests = Request.df_to_request_list(df, service_level)

        print("### Request list created from instances:")
        for r in requests:
            print(r.get_info())
