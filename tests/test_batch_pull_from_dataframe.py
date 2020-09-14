import os
import sys
# Adding project folder to import modules
root = os.getcwd().replace("\\", "/")
sys.path.append(root)

from demand import tripdata_gen as gen
from model.Request import Request

if __name__ == "__main__":

    # Share of each class in customer base
    customer_segmentation_dict = {
        "A": 0.16,
        "B": 0.68,
        "C": 0.16
      }

    # Service quality dict
    service_quality_dict = {
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

    user_classes = list(service_quality_dict.keys())

    df = gen.get_next_batch(
        "TESTE1",
        chunk_size = 2000,
        batch_size = 30,
        tripdata_csv_path='C:\\Users\\LocalAdmin\\OneDrive\\leap_forward\\street_network_server\\input_tripdata\\data\\manhattan-island-new-york-city-new-york-usa\\tripdata\\tripdata_excerpt_2011-2-1_2011-2-28_ids.csv',
        start_timestamp='2011-02-01 00:00:00',
        end_timestamp='2011-02-01 00:01:00',
        classes = user_classes,
        freq = [customer_segmentation_dict[k] for k in user_classes])

    while df is not None:
        if not df.empty:
            print(df.iloc[0].name, " - ", df.iloc[-1].name, "- LEN:", len(df))
            print(df.service_class.value_counts())
            #print(df)
            for row in df.itertuples():
                # revealing = (
                #     row.Index - 
                #     datetime.strptime(
                #         '2011-02-01 00:00:00',
                #         '%Y-%m-%d %H:%M:%S'
                #     )
                # ).total_seconds()

                r = Request(row.Index,
                    service_quality_dict[row.service_class]["pk_delay"],
                    service_quality_dict[row.service_class]["trip_delay"],
                    row.pk_id,
                    row.dp_id,
                    {"P":row.passenger_count},
                    pickup_latitude=row.pickup_latitude,
                    pickup_longitude=row.pickup_longitude,
                    dropoff_latitude=row.dropoff_latitude,
                    dropoff_longitude=row.dropoff_longitude,
                    service_class = row.service_class)

                print(r.get_info())

        df = gen.get_next_batch("TESTE1")