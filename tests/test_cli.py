from pathlib import Path

from datatiles.cli import coords, main


def test_coordinate_parser_handles_points_and_intervals():
    assert coords(["time=2026-08-27T00:00:00Z", "depth=[5,10)"]) == {
        "time":"2026-08-27T00:00:00Z", "depth":("5","10",True,False)}


def test_complete_cli_roundtrip(tmp_path,capsys):
    database=tmp_path/"cli.datatiles"; source=tmp_path/"tile.bin"; output=tmp_path/"out.bin"
    source.write_bytes(b"scientific tile")
    assert main(["init",str(database),"--name","CLI fixture","--format","bin"])==0
    assert main(["add-dimension",str(database),"variable","text"])==0
    assert main(["put",str(database),"1","0","1",str(source),"--coord","variable=depth"])==0
    assert main(["get",str(database),"1","0","1",str(output),"--coord","variable=depth"])==0
    assert output.read_bytes()==source.read_bytes()
    assert main(["select",str(database),"--coord","variable=depth"])==0
    assert main(["contents",str(database)])==0
    assert '"data_type": "raster"' in capsys.readouterr().out
    assert main(["validate",str(database)])==0


def test_cli_missing_tile_has_distinct_exit_status(tmp_path):
    database=tmp_path/"empty.datatiles"; output=tmp_path/"out.bin"
    main(["init",str(database)])
    assert main(["get",str(database),"0","0","0",str(output)])==2
    assert not output.exists()
