import os
import time
import threading
import neovim
import pytest


threading.current_thread().name = "Test"


NVIM_LISTEN_ADDRESS = "/tmp/nvim-LanguageClient-IntegrationTest"
EXPLAIN_ERROR_BUFFER = "__LCNExplainError__"
HOVER_BUFFER = "__LCNHover__"


project_root = os.path.dirname(os.path.abspath(__file__))


def join_path(path: str) -> str:
    """Join path to this project tests root."""
    return os.path.join(project_root, path)


PATH_MAIN_GO = join_path("data/sample-go/main.go")
PATH_OTHER_GO = join_path("data/sample-go/other.go")


def assertRetry(predicate, retry_max=100):
    retry_delay = 0.1
    retry_count = 0

    while retry_count < retry_max:
        if predicate():
            return
        else:
            retry_count += 1
            time.sleep(retry_delay)
    assert predicate()


def getBufferByName(nvim, name: str):
    return [b for b in nvim.buffers if b.name.endswith(name)]


@pytest.fixture(scope="module")
def nvim() -> neovim.Nvim:
    nvim = neovim.attach("socket", path=NVIM_LISTEN_ADDRESS)
    time.sleep(1)
    return nvim


@pytest.fixture(autouse=True)
def setup(nvim):
    nvim.command("%bdelete!")


def test_explainErrorAtPoint(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    nvim.funcs.cursor(26, 2)
    nvim.funcs.LanguageClient_explainErrorAtPoint()
    time.sleep(1)
    buf = getBufferByName(nvim, EXPLAIN_ERROR_BUFFER)[0]
    expect = "1. assign: self-assignment of x to x"

    assert expect in "\n".join(buf)


def test_textDocument_definition(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(2)
    nvim.funcs.cursor(10, 16)
    nvim.funcs.LanguageClient_textDocument_definition()
    time.sleep(3)

    assert nvim.current.window.cursor == [13, 5]


def test_textDocument_hover(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    nvim.funcs.cursor(10, 16)
    nvim.funcs.LanguageClient_textDocument_hover()
    time.sleep(1)
    buf = getBufferByName(nvim, HOVER_BUFFER)[0]
    expect = "func greet() int32"

    assert expect in "\n".join(buf)


def test_textDocument_rename(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    expect = [line.replace("greet", "hello") for line in nvim.current.buffer]
    nvim.funcs.cursor(10, 16)
    nvim.funcs.LanguageClient_textDocument_rename({"newName": "hello"})
    time.sleep(1)

    assert nvim.current.buffer[:] == expect

    nvim.command("edit! {}".format(PATH_MAIN_GO))


def test_textDocument_rename_multiple_oneline(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    expect = [line.replace("someVar", "newVarName")
              for line in nvim.current.buffer]
    nvim.funcs.cursor(18, 2)
    # TODO: Test case where new variable length is different.
    nvim.funcs.LanguageClient_textDocument_rename({"newName": "newVarName"})
    time.sleep(1)

    assert nvim.current.buffer[:] == expect

    nvim.command("bd!")
    nvim.command("edit! {}".format(PATH_MAIN_GO))


def test_textDocument_rename_multiple_files(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    nvim.funcs.cursor(21, 15)
    expect = [line.replace("otherYo", "hello") for line in nvim.current.buffer]
    nvim.funcs.LanguageClient_textDocument_rename({"newName": "hello"})
    time.sleep(1)

    assert nvim.current.buffer[:] == expect

    nvim.command("bd!")
    nvim.command("bd!")
    nvim.command("edit! {}".format(PATH_MAIN_GO))


def test_textDocument_documentSymbol(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    nvim.funcs.cursor(1, 1)
    nvim.funcs.LanguageClient_textDocument_documentSymbol()
    time.sleep(1)

    assert nvim.funcs.getloclist(0)

    nvim.command("1lnext")

    assert nvim.current.window.cursor != [1, 1]


def test_workspace_symbol(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    nvim.funcs.cursor(1, 1)
    nvim.funcs.LanguageClient_workspace_symbol('yo')
    time.sleep(1)

    assert nvim.funcs.getloclist(0)

    nvim.command("lnext")

    assert nvim.current.window.cursor == [24, 5]


def test_textDocument_references(nvim):
    nvim.command("edit! {}".format(PATH_OTHER_GO))
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    nvim.funcs.cursor(13, 6)
    nvim.funcs.LanguageClient_textDocument_references()
    time.sleep(1)
    expect = ["func greet() int32 {", "log.Println(greet())",
              "fmt.Println(greet())"]

    assert [location["text"]
            for location in nvim.funcs.getloclist(0)] == expect

    nvim.command("lnext")

    assert nvim.current.window.cursor == [10, 13]


def test_textDocument_references_modified_buffer(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    nvim.funcs.cursor(13, 6)
    nvim.input("iabc")
    time.sleep(1)
    nvim.funcs.LanguageClient_textDocument_references()
    time.sleep(1)

    nvim.command("lnext")

    # first call to greet in sample-go/other.go
    assert nvim.current.window.cursor == [6, 13]

    nvim.command("edit! {}".format(PATH_MAIN_GO))


def test_languageClient_registerServerCommands(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    nvim.command('let g:responses = []')
    nvim.command("call LanguageClient_registerServerCommands("
                 "{'bash': ['bash']}, g:responses)")
    time.sleep(1)
    assert nvim.vars['responses'][0]['result'] is None


def test_languageClient_registerHandlers(nvim):
    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)
    nvim.command('let g:responses = []')
    nvim.command("call LanguageClient_registerHandlers("
                 "{'window/progress': 'HandleWindowProgress'}, g:responses)")
    time.sleep(1)
    assert nvim.vars['responses'][0]['result'] is None


def _open_float_window(nvim):
    nvim.funcs.cursor(10, 15)
    pos = nvim.funcs.getpos('.')
    nvim.funcs.LanguageClient_textDocument_hover()
    time.sleep(1)
    return pos


def test_textDocument_hover_float_window_closed_on_cursor_moved(nvim):
    if not nvim.funcs.exists("*nvim_open_win"):
        pytest.skip("Neovim 0.3.0 or earlier does not support floating window")

    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)

    buf = nvim.current.buffer

    pos = _open_float_window(nvim)

    float_buf = getBufferByName(nvim, HOVER_BUFFER)[0]

    # Check if float window is open
    float_winnr = nvim.funcs.bufwinnr(float_buf.number)
    assert float_winnr > 0

    # Check if cursor is not moved
    assert buf.number == nvim.current.buffer.number
    assert pos == nvim.funcs.getpos(".")

    # Move cursor to left
    nvim.funcs.cursor(10, 14)

    # Check float window buffer was closed by CursorMoved
    assert len(getBufferByName(nvim, HOVER_BUFFER)) == 0


def test_textDocument_hover_float_window_closed_on_entering_window(nvim):
    if not nvim.funcs.exists("*nvim_open_win"):
        pytest.skip("Neovim 0.3.0 or earlier does not support floating window")

    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)

    win_id = nvim.funcs.win_getid()
    nvim.command("split")
    try:
        assert win_id != nvim.funcs.win_getid()

        _open_float_window(nvim)
        assert win_id != nvim.funcs.win_getid()

        # Move to another window
        nvim.funcs.win_gotoid(win_id)
        assert win_id == nvim.funcs.win_getid()

        # Check float window buffer was closed by BufEnter
        assert len(getBufferByName(nvim, HOVER_BUFFER)) == 0
    finally:
        nvim.command("close!")


def test_textDocument_hover_float_window_closed_on_switching_to_buffer(nvim):
    if not nvim.funcs.exists("*nvim_open_win"):
        pytest.skip("Neovim 0.3.0 or earlier does not support floating window")

    # Create a new buffer
    nvim.command("enew!")

    another_bufnr = nvim.current.buffer.number

    try:
        nvim.command("edit! {}".format(PATH_MAIN_GO))
        time.sleep(1)

        source_bufnr = nvim.current.buffer.number

        _open_float_window(nvim)

        float_buf = getBufferByName(nvim, HOVER_BUFFER)[0]
        float_winnr = nvim.funcs.bufwinnr(float_buf.number)
        assert float_winnr > 0

        assert nvim.current.buffer.number == source_bufnr

        # Move to another buffer within the same window
        nvim.command("buffer {}".format(another_bufnr))
        assert nvim.current.buffer.number == another_bufnr

        # Check float window buffer was closed by BufEnter
        assert len(getBufferByName(nvim, HOVER_BUFFER)) == 0
    finally:
        nvim.command("bdelete! {}".format(another_bufnr))


def test_textDocument_hover_float_window_move_cursor_into_window(nvim):
    if not nvim.funcs.exists("*nvim_open_win"):
        pytest.skip("Neovim 0.3.0 or earlier does not support floating window")

    nvim.command("edit! {}".format(PATH_MAIN_GO))
    time.sleep(1)

    prev_bufnr = nvim.current.buffer.number

    _open_float_window(nvim)

    # Moves cursor into floating window
    nvim.funcs.LanguageClient_textDocument_hover()
    assert nvim.current.buffer.name.endswith("__LCNHover__")

    # Close the window
    nvim.command('close')
    assert nvim.current.buffer.number == prev_bufnr

    # Check float window buffer was closed by :close in the window
    assert len(getBufferByName(nvim, HOVER_BUFFER)) == 0
