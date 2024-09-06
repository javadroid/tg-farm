import aiohttp
import asyncio
import logging
from aiohttp import ClientSession
import platform


# jwt expires in 30 days

MAX_POINTS = 600

FARM_ID = "53b22103-c7ff-413d-bc63-20f6fb806a07"
DROP_GAME_ID = "59bcd12e-04e2-404c-a172-311a0084587d"
DAILY_ID = "fa873d13-d831-4d6f-8aee-9cff7a1d0db1"

logging.basicConfig(level=logging.INFO)


class TomarketGame:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api-web.tomarket.ai/tomarket-game/v1"
        self.headers = {
            "Authorization": f"{self.access_token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        session: ClientSession,
        method: str,
        endpoint: str,
        is_response_json: bool = True,
        **kwargs,
    ):
        url = f"{self.base_url}{endpoint}"
        try:
            async with session.request(
                method, url, headers=self.headers, **kwargs
            ) as response:
                response.raise_for_status()

                if is_response_json:
                    return await response.json()
                else:
                    return await response.text()
        except aiohttp.ClientError as e:
            logging.error(f"Request failed: {e}")
            raise

    async def get_hidden_tasks(self, session: ClientSession):
        data = await self._request(session, "GET", "/tasks/hidden")
        #      [
        #     {
        #         "start": "2024-09-02 14:00:00",
        #         "end": "2024-09-03 14:00:00",
        #         "status": 0, == 0 - unfinished, >1 - finished
        #         "taskId": 1026,
        #         "code": "2,2,3,4",
        #         "score": 2500,
        #         "name": "Mysterious task",
        #         "description": ""
        #     }
        # ]
        return data.get("data")

    async def claim_task(self, session: ClientSession, task_id: int):
        payload = {"task_id": task_id}
        data = await self._request(
            session, "POST", "/tasks/claim", json=payload, is_response_json=False
        )
        #         {
        #   "status": 0,
        #   "message": "",
        #   "data": "ok"
        # }
        return data

    async def start_farming(self, session: ClientSession) -> str:
        data = await self._request(session, "POST", "/farming/start")
        # {
        #     "startTime": 1725178325416,
        #     "endTime": 1725207125416,
        #     "earningsRate": "0.002",
        #     "balance": "0"
        # }
        return data

    async def claim_farming(self, session: ClientSession, farming_id: str):
        data = await self._request(session, "POST", "/farming/claim")
        return data

    async def start_game_session(self, session: ClientSession) -> str:
        payload = {"game_id": DROP_GAME_ID}
        data = await self._request(
            session,
            "POST",
            "/game/play",
            json=payload,
        )
        return data.get("data").get("round_id")

    async def claim_rewards(self, session: ClientSession, game_id: str, points: int):
        payload = {"game_id": game_id, "points": points}
        data = await self._request(
            session, "POST", "/game/claim", json=payload, is_response_json=False
        )
        return data

    async def get_balance(self, session: ClientSession):
        #         {
        #   "status": 0,
        #   "message": "",
        #   "data": {
        #     "available_balance": 2200,
        #     "play_passes": 6,
        #     "timestamp": 1725278717,
        #     "farming": {
        #       "game_id": "53b22103-c7ff-413d-bc63-20f6fb806a07",
        #       "round_id": "503b9f17-7d5d-4bbc-aa01-e4031fc06b4e",
        #       "user_id": 17454567,
        #       "start_at": 1725278438,
        #       "end_at": 1725289238,
        #       "last_claim": 1725278438,
        #       "points": 0
        #     },
        #     "daily": {
        #       "round_id": "9f9fbd79-e378-4c46-bbb6-43e16c2d6b0c",
        #       "user_id": 17454567,
        #       "start_at": 1725249579,
        #       "last_check_ts": 1725249579,
        #       "last_check_ymd": 20240902,
        #       "next_check_ts": 1725292800,
        #       "check_counter": 1,
        #       "today_points": 200,
        #       "today_game": 1
        #     }
        #   }
        # }
        result = await self._request(session, "GET", "/user/balance")
        return result.get("data")

    async def play_game(self):
        async with aiohttp.ClientSession() as session:
            try:
                while True:
                    balance = await self.get_balance(session)
                    current_balance = balance.get("available_balance")
                    current_game_passes = balance.get("play_passes")

                    if current_game_passes <= 0:
                        logging.info("All game passes used, ending game session.")
                        break

                    logging.info(f"Current balance: {current_balance}")
                    logging.info(f"Current game passes: {current_game_passes}")

                    round_id = await self.start_game_session(session)
                    logging.info(
                        f"Game started with ID: {DROP_GAME_ID}\nRound ID: {round_id}"
                    )

                    logging.info("Waiting for game session to end...")
                    await asyncio.sleep(30)  # Wait 30 seconds before claiming

                    result = await self.claim_rewards(
                        session, DROP_GAME_ID, points=MAX_POINTS
                    )
                    logging.info(f"Rewards claimed: {result}")

                    if current_game_passes - 1 == 0:
                        logging.info("All game passes used, ending game session.")
                        break
                    logging.info("Sleeping for 10 seconds before new game...")
                    await asyncio.sleep(10)

            except Exception as e:
                logging.error(f"Unexpected error: {e}")


def main():
    access_token = input("Enter your access token: ").strip()
    game = TomarketGame(access_token)

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(game.play_game())
