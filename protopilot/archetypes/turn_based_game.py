"""Something two people take turns at.

The archetype that proves the axis is real. Its pages are a board and a match
history, not a list and a form, and none of `baseline.py` can produce that —
so it replaces every generator rather than adding to them.

It deliberately needs **nothing the skeleton does not already have**. A grid of
squares where each square is a submit button, re-rendered on every POST, is a
complete two-player board game: no JavaScript, no canvas, no npm, no realtime.
Two people at one browser works exactly as it should. That is why this is the
second archetype and `simulator` is not — a simulator that ticks would need a
static asset the skeleton does not ship, which is a change to a load-bearing
invariant and belongs in its own plan.

The offline generator here is tic-tac-toe by default, and generalises to any
`width × height` board with a `win_length` run. Small enough to be honest,
real enough that the generated suite can take a turn and assert the state
changed — which is the only way to tell a working game from a picture of one.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from protopilot.spec import Spec

NAME = "turn-based-game"
LABEL = "Something two people take turns at"
MATCHES = "chess, checkers, tic-tac-toe, connect four, a card game, anything with turns and a winner"

QUESTIONS = (
    {
        "id": "players",
        "question": "Who is playing?",
        "why": "Two people at one screen is the shape this builds; anything else changes the whole app.",
        "options": ["two people taking turns at one screen", "one person against a simple computer opponent"],
        "recommended": "two people taking turns at one screen",
    },
    {
        "id": "board_shape",
        "question": "What does the board look like?",
        "why": "Sets the grid the board page draws and the win check runs over.",
        "options": ["3x3", "8x8", "7x6 (connect four)", "no board — cards or tokens"],
        "recommended": "3x3",
    },
    {
        "id": "win_condition",
        "question": "How does someone win?",
        "why": "It is the one rule the app has to actually enforce, so it decides what the tests assert.",
        "options": ["a line of three", "a line of four", "capture the other side's piece", "most pieces at the end"],
        "recommended": "a line of three",
    },
    {
        "id": "rules_enforcement",
        "question": "How strict should the rules be?",
        "why": "Full legality checking is most of the build; a shared board that trusts the players is most of the fun.",
        "options": [
            "strict — illegal moves are refused",
            "loose — the board just records what people do",
        ],
        "recommended": "strict — illegal moves are refused",
    },
)

#: Fixed files this archetype adds to the skeleton. Empty, and staying empty:
#: everything here works as a full page reload.
ASSETS: tuple[str, ...] = ()


class Board(BaseModel):
    """This archetype's slice of `spec.extra`.

    Defaults are tic-tac-toe because that is what the offline generator builds
    and what CI therefore exercises. `Spec` stays one loadable type; this model
    owns the shape of its own corner of it.
    """

    width: int = Field(default=3, ge=2, le=12)
    height: int = Field(default=3, ge=2, le=12)
    win_length: int = Field(default=3, ge=2, le=12)
    pieces: list[str] = Field(default_factory=lambda: ["X", "O"])

    @property
    def cells(self) -> int:
        return self.width * self.height


EXTRA = Board


def board_of(spec: Spec) -> Board:
    """The board this spec asks for, however incompletely it asks.

    Never raises. `spec.extra` can be empty (a spec from before this archetype
    existed), partial, or hand-edited nonsense, and the answer to all three is
    the same: a playable default beats a traceback at generation time.
    """
    try:
        return Board.model_validate(spec.extra or {})
    except Exception:  # noqa: BLE001 -- any invalid shape falls back
        return Board()


def screens(spec: Spec) -> list[dict]:
    """A board and a history. Deliberately not the CRUD spread.

    There is no `form` screen: you do not fill in a form to make a move, you
    press a square. That absence is the whole point of the archetype existing —
    `crud.screens()` cannot express a page like this.
    """
    return [
        {"name": "Home", "path": "/", "entity": None, "kind": "custom"},
        {"name": "Board", "path": "/board", "entity": None, "kind": "custom"},
        {"name": "Matches", "path": "/matches", "entity": "Match", "kind": "list"},
        {"name": "Match detail", "path": "/matches/{row_id}", "entity": "Match", "kind": "detail"},
    ]


def brief() -> str:
    board = Board()
    return (
        "This is a turn-based game two people play at one screen, taking turns\n"
        "in the same browser. The centre of the app is the board page.\n"
        "\n"
        "Build the board as a grid of plain submit buttons inside one form: one\n"
        "button per square, posting the square it represents. The page re-renders\n"
        "after every move. That is the whole interaction model -- no JavaScript,\n"
        "no drag and drop, no polling. It works, and it is how a board game is\n"
        "built on this stack.\n"
        "\n"
        "Draw the pieces as inline SVG. Real vector shapes, hand-drawn in the\n"
        "template -- not emoji, and not an image file. A piece is a few paths;\n"
        "draw them.\n"
        "\n"
        "State lives in one row: the board as a string, whose turn it is, and\n"
        "whether anyone has won. Never in the session, never in a global, never\n"
        "only in the page -- a refresh must show the same game.\n"
        "\n"
        "The board page must say whose turn it is and announce a win when there\n"
        f"is one. Default board is {board.width}x{board.height} with a line of\n"
        f"{board.win_length} to win, unless the spec says otherwise."
    )


# ── the offline generator ────────────────────────────────────────────────
#
# Every one of these replaces the `baseline.py` function of the same name. See
# `archetypes/__init__.py::generator` for how they are found.

BANNER = "# GENERATED by proto-pilot -- edited by hand only after you stop generating.\n"


def models_py(spec: Spec) -> str:
    board = board_of(spec)
    return (
        BANNER + "from __future__ import annotations\n\n"
        "from sqlalchemy import Boolean, Integer, String\n"
        "from sqlalchemy.orm import Mapped, mapped_column\n\n"
        "from app.db import Base\n\n"
        f"WIDTH = {board.width}\n"
        f"HEIGHT = {board.height}\n"
        f"WIN_LENGTH = {board.win_length}\n"
        f"PIECES = {board.pieces!r}\n"
        'EMPTY = "."\n\n\n'
        "class Match(Base):\n"
        '    """One game. The whole of the state, in one row.\n\n'
        "    The board is a flat string of WIDTH*HEIGHT characters so a refresh\n"
        "    shows the same game -- state in a session or a module global would\n"
        "    survive neither a reload nor a second player.\n"
        '    """\n\n'
        '    __tablename__ = "matches"\n\n'
        "    id: Mapped[int] = mapped_column(primary_key=True)\n"
        "    board: Mapped[str] = mapped_column(String(WIDTH * HEIGHT), nullable=False)\n"
        "    turn: Mapped[str] = mapped_column(String(4), nullable=False)\n"
        '    winner: Mapped[str] = mapped_column(String(8), nullable=False, default="")\n'
        "    finished: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)\n"
        "    moves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)\n\n"
        "    @property\n"
        "    def rows(self) -> list[list[dict]]:\n"
        '        """The board as rows of cells, ready for the template."""\n'
        "        out = []\n"
        "        for y in range(HEIGHT):\n"
        "            row = []\n"
        "            for x in range(WIDTH):\n"
        "                index = y * WIDTH + x\n"
        '                row.append({"index": index, "piece": self.board[index]})\n'
        "            out.append(row)\n"
        "        return out\n\n"
        "    @property\n"
        "    def display(self) -> str:\n"
        "        if self.winner:\n"
        '            return f"Match {self.id} -- {self.winner} won"\n'
        '        return f"Match {self.id} -- {self.turn} to play"\n\n'
        "    def __str__(self) -> str:\n"
        "        return self.display\n"
    )


def seed_py(spec: Spec) -> str:
    board = board_of(spec)
    first, second = (board.pieces + ["X", "O"])[:2]
    return (
        BANNER + "from __future__ import annotations\n\n"
        "from sqlalchemy import func, select\n"
        "from sqlalchemy.orm import Session\n\n"
        "from app.models import EMPTY, HEIGHT, WIDTH, Match\n\n\n"
        "def seed(db: Session) -> None:\n"
        '    """One finished game, then one in progress.\n\n'
        "    The ORDER is load-bearing: the board page shows the most recent\n"
        "    match, so the playable one has to be the newer row. Seeded the other\n"
        "    way round the app opens on a finished game and every move is refused,\n"
        "    which looks exactly like a broken board.\n\n"
        "    Both rows matter -- the finished one stops the history page being\n"
        "    blank on arrival, the open one is what makes /board playable.\n"
        "    Guarded, so a restart does not stack up games.\n"
        '    """\n'
        "    if db.scalar(select(func.count()).select_from(Match)):\n"
        "        return\n\n"
        "    blank = EMPTY * (WIDTH * HEIGHT)\n\n"
        "    played = list(blank)\n"
        f'    for index, piece in enumerate(["{first}", "{second}", "{first}", "{second}", "{first}"][: WIDTH * HEIGHT]):\n'
        "        played[index] = piece\n"
        "    db.add(\n"
        "        Match(\n"
        '            board="".join(played),\n'
        f'            turn="{second}",\n'
        f'            winner="{first}",\n'
        "            finished=True,\n"
        "            moves=5,\n"
        "        )\n"
        "    )\n"
        "    db.flush()\n\n"
        f'    db.add(Match(board=blank, turn="{first}", winner="", finished=False, moves=0))\n'
        "    db.commit()\n"
    )


def routes_py(spec: Spec) -> str:
    board = board_of(spec)
    first = (board.pieces + ["X"])[0]
    return (
        BANNER + "from __future__ import annotations\n\n"
        "from fastapi import APIRouter, Depends, Form, HTTPException, Request\n"
        "from fastapi.responses import HTMLResponse, RedirectResponse\n"
        "from sqlalchemy import select\n"
        "from sqlalchemy.orm import Session\n\n"
        "from app.db import get_db\n"
        "from app.models import EMPTY, HEIGHT, PIECES, WIDTH, WIN_LENGTH, Match\n"
        "from app.templating import templates\n\n"
        "router = APIRouter()\n\n\n"
        "def _lines() -> list[list[int]]:\n"
        '    """Every run of WIN_LENGTH cells, in all four directions."""\n'
        "    out = []\n"
        "    for y in range(HEIGHT):\n"
        "        for x in range(WIDTH):\n"
        "            for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):\n"
        "                end_x, end_y = x + dx * (WIN_LENGTH - 1), y + dy * (WIN_LENGTH - 1)\n"
        "                if 0 <= end_x < WIDTH and 0 <= end_y < HEIGHT:\n"
        "                    out.append(\n"
        "                        [(y + dy * i) * WIDTH + (x + dx * i) for i in range(WIN_LENGTH)]\n"
        "                    )\n"
        "    return out\n\n\n"
        "LINES = _lines()\n\n\n"
        "def winner_of(board: str) -> str:\n"
        '    """The piece occupying a full line, or an empty string."""\n'
        "    for line in LINES:\n"
        "        first = board[line[0]]\n"
        "        if first != EMPTY and all(board[i] == first for i in line):\n"
        "            return first\n"
        '    return ""\n\n\n'
        "def current(db: Session) -> Match:\n"
        '    """The game on the board: the most recent one, finished or not.\n\n'
        "    Deliberately NOT the most recent *unfinished* game. That version\n"
        "    replaced the board with a fresh empty one the instant somebody won,\n"
        "    so the result was never visible -- you played the winning move and\n"
        "    the page showed you a new game. Found by playing it; the smoke suite\n"
        "    had passed, because it never played as far as a win.\n"
        '    """\n'
        "    match = db.scalars(select(Match).order_by(Match.id.desc()).limit(1)).first()\n"
        "    if match is None:\n"
        f'        match = Match(board=EMPTY * (WIDTH * HEIGHT), turn=PIECES[0], winner="", finished=False, moves=0)\n'
        "        db.add(match)\n"
        "        db.commit()\n"
        "        db.refresh(match)\n"
        "    return match\n\n\n"
        '@router.get("/", response_class=HTMLResponse)\n'
        "def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:\n"
        "    finished = db.scalars(select(Match).where(Match.finished.is_(True)).order_by(Match.id.desc())).all()\n"
        "    return templates.TemplateResponse(\n"
        '        request, "index.html", {"match": current(db), "finished": finished}\n'
        "    )\n\n\n"
        '@router.get("/board", response_class=HTMLResponse)\n'
        "def board(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:\n"
        '    return templates.TemplateResponse(request, "board.html", {"match": current(db)})\n\n\n'
        '@router.post("/board/play")\n'
        "def play(cell: str = Form(...), db: Session = Depends(get_db)) -> RedirectResponse:\n"
        '    """Take a turn. An illegal move changes nothing and says so by\n'
        "    redirecting to the same board -- a refused move must not 500, and it\n"
        '    must not silently look like it worked either."""\n'
        "    match = current(db)\n"
        "    try:\n"
        "        index = int(cell)\n"
        "    except (TypeError, ValueError):\n"
        '        return RedirectResponse("/board", status_code=303)\n'
        "    if not (0 <= index < WIDTH * HEIGHT) or match.board[index] != EMPTY or match.finished:\n"
        '        return RedirectResponse("/board", status_code=303)\n\n'
        "    cells = list(match.board)\n"
        "    cells[index] = match.turn\n"
        '    match.board = "".join(cells)\n'
        "    match.moves += 1\n\n"
        "    won = winner_of(match.board)\n"
        "    if won:\n"
        "        match.winner, match.finished = won, True\n"
        "    elif EMPTY not in match.board:\n"
        '        match.winner, match.finished = "draw", True\n'
        "    else:\n"
        "        match.turn = PIECES[match.moves % len(PIECES)]\n"
        "    db.commit()\n"
        '    return RedirectResponse("/board", status_code=303)\n\n\n'
        '@router.post("/board/new")\n'
        "def new_game(db: Session = Depends(get_db)) -> RedirectResponse:\n"
        '    """Start a fresh game, leaving the finished one in the history."""\n'
        '    db.add(Match(board=EMPTY * (WIDTH * HEIGHT), turn=PIECES[0], winner="", finished=False, moves=0))\n'
        "    db.commit()\n"
        '    return RedirectResponse("/board", status_code=303)\n\n\n'
        '@router.get("/matches", response_class=HTMLResponse)\n'
        "def matches_list(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:\n"
        "    rows = db.scalars(select(Match).order_by(Match.id.desc())).all()\n"
        '    return templates.TemplateResponse(request, "matches_list.html", {"rows": rows})\n\n\n'
        '@router.get("/matches/{row_id}", response_class=HTMLResponse)\n'
        "def match_detail(row_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:\n"
        "    row = db.get(Match, row_id)\n"
        "    if row is None:\n"
        '        raise HTTPException(status_code=404, detail="no such match")\n'
        '    return templates.TemplateResponse(request, "matches_detail.html", {"row": row})\n'
    )


def smoke_py(spec: Spec) -> str:
    """Generated before the routes, from the spec.

    The test that matters is `test_playing_a_square_changes_the_board`. Every
    other check here would pass against a static picture of a board; that one
    is the difference between a game and a screenshot of one.
    """
    return (
        BANNER + "from __future__ import annotations\n\n"
        "from sqlalchemy import select\n\n"
        "from app.models import EMPTY, Match\n"
        "from app.routes import LINES\n\n\n"
        "def test_index_renders(client) -> None:\n"
        '    response = client.get("/")\n'
        "    assert response.status_code == 200, response.text\n\n\n"
        "def test_board_renders(client) -> None:\n"
        '    response = client.get("/board")\n'
        "    assert response.status_code == 200, response.text\n\n\n"
        "def test_a_game_is_seeded(db) -> None:\n"
        '    """A prototype with no game in it cannot be demonstrated."""\n'
        "    assert db.scalars(select(Match)).first() is not None\n\n\n"
        "def test_playing_a_square_changes_the_board(client, db) -> None:\n"
        '    """The one test a static page could not pass."""\n'
        "    before = db.scalars(select(Match).where(Match.finished.is_(False))).first()\n"
        '    assert before is not None, "no game in progress to play"\n'
        "    empty_index = before.board.index(EMPTY)\n\n"
        '    response = client.post("/board/play", data={"cell": str(empty_index)}, follow_redirects=True)\n'
        "    assert response.status_code == 200, response.text\n\n"
        "    db.rollback()\n"
        "    after = db.get(Match, before.id)\n"
        "    assert after is not None\n"
        '    assert after.board[empty_index] != EMPTY, "the move did not land on the board"\n'
        '    assert after.moves == 1, "the move was not counted"\n\n\n'
        "def test_playing_an_occupied_square_is_refused(client, db) -> None:\n"
        '    """It must not 500, and it must not silently look like it worked."""\n'
        "    match = db.scalars(select(Match).where(Match.finished.is_(False))).first()\n"
        "    assert match is not None\n"
        "    taken = match.board.index(EMPTY)\n"
        '    client.post("/board/play", data={"cell": str(taken)}, follow_redirects=True)\n'
        "    db.rollback()\n"
        "    moves_after_first = db.get(Match, match.id).moves\n\n"
        '    client.post("/board/play", data={"cell": str(taken)}, follow_redirects=True)\n'
        "    db.rollback()\n"
        "    assert db.get(Match, match.id).moves == moves_after_first\n\n\n"
        "def test_an_out_of_range_square_does_not_crash(client) -> None:\n"
        '    response = client.post("/board/play", data={"cell": "9999"}, follow_redirects=True)\n'
        "    assert response.status_code == 200, response.text\n\n\n"
        "def test_playing_to_a_win_shows_the_result(client, db) -> None:\n"
        '    """The test that a static page and a half-working one both fail.\n\n'
        "    Every other check here would pass against a board that silently\n"
        "    resets when somebody wins: this one plays a full line and asserts\n"
        "    the winner is still on the page afterwards.\n\n"
        "    It starts its own game rather than using the seeded one. The suite\n"
        "    shares a database and earlier tests have already put pieces on that\n"
        "    board, so a test that assumed an empty grid would pass or fail on\n"
        "    the order it happened to run in.\n"
        '    """\n'
        '    client.post("/board/new", follow_redirects=True)\n'
        "    db.rollback()\n"
        "    match = db.scalars(select(Match).order_by(Match.id.desc()).limit(1)).first()\n"
        '    assert match is not None and match.board.count(EMPTY) == len(match.board), "new game is not empty"\n\n'
        "    line = LINES[0]\n"
        "    others = [i for i in range(len(match.board)) if i not in line]\n"
        "    for step, cell in enumerate(line):\n"
        '        client.post("/board/play", data={"cell": str(cell)}, follow_redirects=True)\n'
        "        if step < len(line) - 1:\n"
        '            client.post("/board/play", data={"cell": str(others[step])}, follow_redirects=True)\n\n'
        "    db.rollback()\n"
        "    played = db.get(Match, match.id)\n"
        '    assert played.winner, "a completed line did not register a winner"\n'
        '    assert played.finished, "the game did not end"\n'
        '    page = client.get("/board")\n'
        '    assert played.winner in page.text, "the board page does not show the result"\n\n\n'
        "def test_matches_list_renders(client) -> None:\n"
        '    response = client.get("/matches")\n'
        "    assert response.status_code == 200, response.text\n\n\n"
        "def test_match_detail_renders(client, db) -> None:\n"
        "    row = db.scalars(select(Match).order_by(Match.id).limit(1)).first()\n"
        "    assert row is not None\n"
        '    response = client.get(f"/matches/{row.id}")\n'
        "    assert response.status_code == 200, response.text\n\n\n"
        "def test_unknown_match_is_404(client) -> None:\n"
        '    assert client.get("/matches/99999999").status_code == 404\n'
    )


_BOARD = """{% extends "base.html" %}
{% block title %}Board{% endblock %}
{% block content %}
  <h1>Board</h1>
  {% if match.winner %}
    <p class="pill done">{% if match.winner == 'draw' %}A draw{% else %}{{ match.winner }} wins{% endif %}</p>
  {% else %}
    <p class="muted">{{ match.turn }} to play</p>
  {% endif %}

  <form method="post" action="/board/play">
    <table class="board" style="border-collapse:collapse">
      {% for row in match.rows %}
      <tr>
        {% for cell in row %}
        <td style="padding:0;border:1px solid var(--line)">
          <button type="submit" name="cell" value="{{ cell.index }}"
                  style="width:64px;height:64px;display:block;background:none;border:0;cursor:pointer"
                  {% if cell.piece != '.' or match.winner %}disabled{% endif %}
                  aria-label="square {{ cell.index }}">
            {% if cell.piece == '.' %}
              <svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true"></svg>
            {% elif cell.piece == first_piece %}
              <svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">
                <line x1="9" y1="9" x2="31" y2="31" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>
                <line x1="31" y1="9" x2="9" y2="31" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>
              </svg>
            {% else %}
              <svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">
                <circle cx="20" cy="20" r="12" fill="none" stroke="currentColor" stroke-width="5"/>
              </svg>
            {% endif %}
          </button>
        </td>
        {% endfor %}
      </tr>
      {% endfor %}
    </table>
  </form>

  <form method="post" action="/board/new" style="margin-top:14px">
    <button type="submit">New game</button>
  </form>
{% endblock %}"""


_INDEX = """{% extends "base.html" %}
{% block content %}
  <h1>{{ app_name }}</h1>
  <p class="muted">{{ app_purpose }}</p>
  <p><a class="btn primary" href="/board">
    {% if match.winner %}Start a new game{% else %}{{ match.turn }} to play &mdash; open the board{% endif %}
  </a></p>
  <h2>Finished games</h2>
  {% if finished %}
  <ul>{% for m in finished %}<li><a href="/matches/{{ m.id }}">{{ m.display }}</a></li>{% endfor %}</ul>
  {% else %}<p class="muted">Nobody has finished a game yet.</p>{% endif %}
{% endblock %}"""


_NAV = """<nav>
  <a href="/board">Board</a>
  <a href="/matches">Matches</a>
</nav>"""


_LIST = """{% extends "base.html" %}
{% block title %}Matches{% endblock %}
{% block content %}
  <h1>Matches</h1>
  {% if rows %}
  <table>
    <tr><th>Game</th><th>Moves</th><th>Result</th></tr>
    {% for row in rows %}
    <tr>
      <td><a href="/matches/{{ row.id }}">Match {{ row.id }}</a></td>
      <td>{{ row.moves }}</td>
      <td>{% if row.winner %}{{ row.winner }}{% else %}in progress{% endif %}</td>
    </tr>
    {% endfor %}
  </table>
  {% else %}<p class="muted">No games yet. <a href="/board">Start one.</a></p>{% endif %}
{% endblock %}"""


_DETAIL = """{% extends "base.html" %}
{% block title %}Match {{ row.id }}{% endblock %}
{% block content %}
  <h1>Match {{ row.id }}</h1>
  <p class="muted">{{ row.display }} &middot; {{ row.moves }} move(s)</p>
  <table class="board" style="border-collapse:collapse">
    {% for line in row.rows %}
    <tr>
      {% for cell in line %}
      <td style="width:48px;height:48px;border:1px solid var(--line);text-align:center">
        {% if cell.piece != '.' %}{{ cell.piece }}{% endif %}
      </td>
      {% endfor %}
    </tr>
    {% endfor %}
  </table>
  <p style="margin-top:12px"><a href="/matches">All matches</a></p>
{% endblock %}"""


def templates_for(spec: Spec) -> dict[str, str]:
    board = board_of(spec)
    first = (board.pieces + ["X"])[0]
    return {
        "app/templates/_nav.html": _NAV,
        "app/templates/index.html": _INDEX,
        # `first_piece` is baked in rather than passed by the route: the board
        # template is the only place that needs it, and a context key a route
        # forgets to pass is the most common way a generated app 500s.
        "app/templates/board.html": _BOARD.replace("first_piece", f"'{first}'"),
        "app/templates/matches_list.html": _LIST,
        "app/templates/matches_detail.html": _DETAIL,
    }
