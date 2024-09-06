import aiohttp
import asyncio
import logging
from aiohttp import ClientSession
import platform


MAX_POINTS = 280

logging.basicConfig(level=logging.INFO)


class BlumGame:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://game-domain.blum.codes/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
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
        data = await self._request(session, "POST", "/game/play")
        return data.get("gameId")

    async def claim_rewards(self, session: ClientSession, game_id: str, points: int):
        payload = {"gameId": game_id, "points": points}
        data = await self._request(
            session, "POST", "/game/claim", json=payload, is_response_json=False
        )
        return data

    async def get_balance(self, session: ClientSession):
        return await self._request(session, "GET", "/user/balance")

    async def play_game(self):
        async with aiohttp.ClientSession() as session:
            try:
                while True:
                    balance = await self.get_balance(session)
                    current_balance = balance.get("availableBalance")
                    current_game_passes = balance.get("playPasses")

                    if current_game_passes <= 0:
                        logging.info("All game passes used, ending game session.")
                        break

                    logging.info(f"Current balance: {current_balance}")
                    logging.info(f"Current game passes: {current_game_passes}")

                    game_id = await self.start_game_session(session)
                    logging.info(f"Game started with ID: {game_id}")

                    logging.info("Waiting for game session to end...")
                    await asyncio.sleep(30)  # Wait 30 seconds before claiming

                    result = await self.claim_rewards(
                        session, game_id, points=MAX_POINTS
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
    blum_game = BlumGame(access_token)

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(blum_game.play_game())
