import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from rpa_docs import drive


class DriveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = MagicMock()
        self.files = self.service.files.return_value
        self.credentials_patch = patch.object(drive, "credentials", return_value=object())
        self.build_patch = patch("googleapiclient.discovery.build", return_value=self.service)
        self.credentials_patch.start()
        self.build_patch.start()

    def tearDown(self):
        self.build_patch.stop()
        self.credentials_patch.stop()
        self.temporary.cleanup()

    def test_file_picker_reads_all_pages_and_filters_non_media(self):
        self.files.list.return_value.execute.side_effect = [
            {"files": [{"id": "a", "name": "a.mp4", "mimeType": "video/mp4"}, {"id": "text", "mimeType": "text/plain"}], "nextPageToken": "page-two"},
            {"files": [{"id": "b", "name": "videos.zip", "mimeType": "application/zip"}, {"id": "folder", "mimeType": "application/vnd.google-apps.folder"}]},
        ]
        result = drive.list_files("folder-id")
        self.assertEqual([item["id"] for item in result], ["a", "b", "folder"])
        self.assertNotIn("pageToken", self.files.list.call_args_list[0].kwargs)
        self.assertEqual(self.files.list.call_args_list[1].kwargs["pageToken"], "page-two")
        self.assertTrue(self.files.list.call_args.kwargs["includeItemsFromAllDrives"])

    def test_query_escapes_quotes_and_backslashes_in_both_inputs(self):
        self.files.list.return_value.execute.return_value = {"files": []}
        drive.list_files("id' OR \\ test", "nome'\\test")
        query = self.files.list.call_args.kwargs["q"]
        self.assertEqual(query, "'id\\' OR \\\\ test' in parents and trashed = false and name contains 'nome\\'\\\\test'")

    def test_repeated_page_token_does_not_loop_forever(self):
        self.files.list.return_value.execute.return_value = {"files": [], "nextPageToken": "same-page"}
        self.assertEqual(drive.list_files(), [])
        self.assertEqual(self.files.list.call_count, 2)

    def install_download(self, metadata, fail=False):
        self.files.get.return_value.execute.side_effect = metadata
        self.files.get_media.side_effect = lambda **kwargs: kwargs["fileId"].encode()
        class Downloader:
            def __init__(self, stream, request, chunksize):
                self.stream, self.request = stream, request
            def next_chunk(self):
                self.stream.write(self.request)
                if fail:
                    raise RuntimeError("Download interrupted")
                return None, True
        return patch("googleapiclient.http.MediaIoBaseDownload", Downloader)

    def test_same_filename_does_not_overwrite_another_recording(self):
        metadata = [{"name": "reuniao.mp4", "mimeType": "video/mp4"}] * 2
        with self.install_download(metadata):
            result = drive.download_files(["first-id", "second-id", "first-id"], self.root)
        self.assertEqual([path.name for path in result], ["reuniao.mp4", "reuniao-2.mp4"])
        self.assertEqual([path.read_bytes() for path in result], [b"first-id", b"second-id"])
        self.assertEqual(self.files.get.call_count, 2)
        self.assertEqual(list(self.root.glob("*.part")), [])

    def test_download_failure_never_leaves_a_partial_video(self):
        with self.install_download([{"name": "reuniao.mp4", "mimeType": "video/mp4"}], fail=True):
            with self.assertRaises(RuntimeError):
                drive.download_files(["first-id"], self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_remote_path_escape_is_rejected_before_download(self):
        with self.install_download([{"name": "../outside.mp4", "mimeType": "video/mp4"}]):
            with self.assertRaises(Exception):
                drive.download_files(["first-id"], self.root)
        self.files.get_media.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
