import datetime as dt
import zipfile

import pandas as pd
from shapely.geometry import box

from src.ingest.offer import (active_services, gtfs_stop_frequencies, last_valid_weekday, pick_weekday,
                              route_mode, trip_departures)

CAL = pd.DataFrame({"service_id": ["sem", "we"], "monday": ["1", "0"], "tuesday": ["1", "0"],
                    "wednesday": ["1", "0"], "thursday": ["1", "0"], "friday": ["1", "0"],
                    "saturday": ["0", "1"], "sunday": ["0", "1"],
                    "start_date": ["20300101", "20300101"], "end_date": ["20301231", "20301231"]})
# 2030-01-08 (mardi) : service "sem" supprimé (jour férié fictif), service "extra" ajouté
CAL_DATES = pd.DataFrame({"service_id": ["sem", "extra"], "date": ["20300108", "20300108"],
                          "exception_type": ["2", "1"]})


def test_route_mode_standard_and_extended():
    assert [route_mode(x) for x in ("0", "1", "2", "3", "6", "702", "109", "abc")] == \
           ["tram", "metro", "train", "bus", "telepherique", "bus", "train", None]


def test_active_services_with_exceptions():
    assert active_services(CAL, CAL_DATES, dt.date(2030, 1, 1)) == {"sem"}          # mardi normal
    assert active_services(CAL, CAL_DATES, dt.date(2030, 1, 8)) == {"extra"}        # exceptions
    assert active_services(CAL, CAL_DATES, dt.date(2030, 1, 5)) == {"we"}           # samedi


def test_pick_weekday_avoids_reduced_day():
    trips = pd.DataFrame({"service_id": ["sem"] * 10 + ["extra"], "trip_id": map(str, range(11))})
    day = pick_weekday(CAL, CAL_DATES, trips)
    assert day.weekday() == 1 and day != dt.date(2030, 1, 8)
    assert pick_weekday(CAL, CAL_DATES, trips, forced="2030-01-15") == dt.date(2030, 1, 15)


def test_gtfs_stop_frequencies(tmp_path):
    files = {
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon,location_type\n"
                     "A,Gare,45.19,5.71,0\nB,Victor Hugo,45.19,5.72,0\nP,Station parente,45.19,5.71,1\n"
                     "X,Lyon,45.76,4.83,0\n",
        "routes.txt": "route_id,route_type\nT1,0\nB1,3\n",
        "trips.txt": "route_id,service_id,trip_id\nT1,sem,t1\nT1,sem,t2\nB1,sem,b1\nB1,we,b2\n",
        "calendar.txt": CAL.to_csv(index=False),
        "stop_times.txt": "trip_id,stop_id,stop_sequence\nt1,A,1\nt1,B,2\nt2,A,1\nt2,B,2\nb1,A,1\nb2,A,1\nt1,X,3\n",
    }
    path = tmp_path / "test__1.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    df, info = gtfs_stop_frequencies(path, box(5.6, 45.1, 5.8, 45.3), forced_day="2030-01-01")
    got = {(r.stop_id, r.type): r.passages_jour for r in df.itertuples()}
    # A : 2 passages tram + 1 bus (b2 = week-end exclu) ; B : 2 tram ; X hors zone ; P station parente ignorée
    assert got == {("A", "tram"): 2, ("A", "bus"): 1, ("B", "tram"): 2}
    assert info["arrets_zone"] == 2 and info["jour_type"] == "2030-01-01"


def test_trip_departures_from_frequencies():
    freq = pd.DataFrame({"trip_id": ["c", "c", "d"], "start_time": ["11:00:00", "20:00:00", "06:00:00"],
                         "end_time": ["19:00:00", "20:30:00", "06:10:00"], "headway_secs": ["300", "600", "900"]})
    # c : 8 h / 5 min = 96 + 30 min / 10 min = 3 ; d : 10 min / 15 min -> 1 départ minimum
    assert trip_departures(freq).to_dict() == {"c": 99, "d": 1}


def test_expired_feed_uses_its_own_validity():
    trips = pd.DataFrame({"service_id": ["sem"] * 3, "trip_id": ["1", "2", "3"]})
    day = last_valid_weekday(CAL, CAL_DATES, trips)          # validité jusqu'au 31/12/2030
    assert day.weekday() == 1 and dt.date(2030, 11, 1) <= day <= dt.date(2030, 12, 31)


def test_all_stops_when_no_area(tmp_path):
    files = {"stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nA,Fort-de-France,14.6,-61.07\n",
             "routes.txt": "route_id,route_type\nB1,3\n", "trips.txt": "route_id,service_id,trip_id\nB1,sem,b1\n",
             "calendar.txt": CAL.to_csv(index=False), "stop_times.txt": "trip_id,stop_id\nb1,A\n"}
    path = tmp_path / "drom__1.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    from src.national.common import bbox_territory
    mask = lambda lon, lat: pd.Series(bbox_territory(lon.astype(float).to_numpy(), lat.astype(float).to_numpy()) != "", index=lon.index)  # noqa: E731
    df, info = gtfs_stop_frequencies(path, None, forced_day="2030-01-01", coord_mask=mask)
    assert df.passages_jour.tolist() == [1] and info["arrets_zone"] == 1
    df2, _ = gtfs_stop_frequencies(path, None, forced_day="2030-01-01")   # filtre métropole par défaut : exclu
    assert df2.empty
