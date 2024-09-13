import secrets
import asyncio
import logging
import random
import itertools
import datetime

from curl_cffi import requests
import platform

DEFAULT_NONCE = secrets.token_hex(32)
MAX_TAPS_COUNT = 1000
TURBO_BOOST_DAMAGE_MULTIPLIER = 10
TURBO_BOOST_DURATION = TURBO_BOOST_DAMAGE_MULTIPLIER

COMBO_SEQUENCE_LENGTH = 4

MAX_BOSS_LEVEL = 15

DEFAULT_SPIN_COUNT = 10 

logging.basicConfig(level=logging.INFO)


class MemefiGame:
    def __init__(
        self,
        jwt_token: str,
        initial_nonce: str | None = None,
        max_allowed_turbo_boosts: int = 0,
        max_allowed_recharge_boosts: int = 0,
        tap_bot: bool = False,
        allow_spin: bool = False
    ):
        self.jwt_token = jwt_token
        self.url = "https://api-gw-tg.memefi.club/graphql"
        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json",
            # "Accept": "*/*",
            # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36",
        }
        self.nonce = initial_nonce if initial_nonce else DEFAULT_NONCE
        self.max_allowed_turbo_boosts = max_allowed_turbo_boosts
        self.max_allowed_recharge_boosts = max_allowed_recharge_boosts
        self.tap_bot = tap_bot
        self.allow_spin = allow_spin

        if self.max_allowed_turbo_boosts < 0:
            raise ValueError("Max allowed turbo boosts must be a positive integer")

    async def _request(
        self, session: requests.AsyncSession, method: str, payload: dict | list
    ):
        try:
            response = await session.request(
                method,
                self.url,
                headers=self.headers,
                json=payload,
                impersonate="chrome",
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestsError as e:
            logging.error(f"Request failed: {e}")
            raise

    def generate_vector(self, taps_count: int) -> str:
        vector = [random.randint(1, 4) for _ in range(taps_count)]
        return ",".join(map(str, vector))

    async def get_game_config(self, session: requests.AsyncSession):
        payload = [
            {
                "operationName": "QUERY_GAME_CONFIG",
                "variables": {},
                "query": "query QUERY_GAME_CONFIG {\n  telegramGameGetConfig {\n    ...FragmentBossFightConfig\n    __typename\n  }\n}\n\nfragment FragmentBossFightConfig on TelegramGameConfigOutput {\n  _id\n  coinsAmount\n  currentEnergy\n  maxEnergy\n  weaponLevel\n  zonesCount\n  tapsReward\n  energyLimitLevel\n  energyRechargeLevel\n  tapBotLevel\n  currentBoss {\n    _id\n    level\n    currentHealth\n    maxHealth\n    __typename\n  }\n  freeBoosts {\n    _id\n    currentTurboAmount\n    maxTurboAmount\n    turboLastActivatedAt\n    turboAmountLastRechargeDate\n    currentRefillEnergyAmount\n    maxRefillEnergyAmount\n    refillEnergyLastActivatedAt\n    refillEnergyAmountLastRechargeDate\n    __typename\n  }\n  bonusLeaderDamageEndAt\n  bonusLeaderDamageStartAt\n  bonusLeaderDamageMultiplier\n  nonce\n  spinEnergyNextRechargeAt\n  spinEnergyNonRefillable\n  spinEnergyRefillable\n  spinEnergyTotal\n  spinEnergyStaticLimit\n  __typename\n}",
            }
        ]

        result = await self._request(session, "POST", payload)
        return result[0]["data"]["telegramGameGetConfig"]

    async def get_tap_bot_config(self, session: requests.AsyncSession):
        payload = [
            {
                "operationName": "TapbotConfig",
                "variables": {},
                "query": "fragment FragmentTapBotConfig on TelegramGameTapbotOutput {\n  damagePerSec\n  endsAt\n  id\n  isPurchased\n  startsAt\n  totalAttempts\n  usedAttempts\n  __typename\n}\n\nquery TapbotConfig {\n  telegramGameTapbotGetConfig {\n    ...FragmentTapBotConfig\n    __typename\n  }\n}",
            }
        ]

        result = await self._request(session, "POST", payload)
        #  "telegramGameTapbotGetConfig": {
        #         "damagePerSec": 24,
        #         "endsAt": "2024-09-02T17:57:27.000Z", // or null
        #         "id": "2", // or "0"
        #         "isPurchased": true,
        #         "startsAt": "2024-09-02T14:57:27.000Z", // or null
        #         "totalAttempts": 3,
        #         "usedAttempts": 2,
        #         "__typename": "TelegramGameTapbotOutput"
        #     }
        return result[0]["data"]["telegramGameTapbotGetConfig"]

    async def start_tap_bot(self, session: requests.AsyncSession):
        payload = [
            {
                "operationName": "TapbotStart",
                "variables": {},
                "query": "fragment FragmentTapBotConfig on TelegramGameTapbotOutput {\n  damagePerSec\n  endsAt\n  id\n  isPurchased\n  startsAt\n  totalAttempts\n  usedAttempts\n  __typename\n}\n\nmutation TapbotStart {\n  telegramGameTapbotStart {\n    ...FragmentTapBotConfig\n    __typename\n  }\n}",
            }
        ]
        result = await self._request(session, "POST", payload)
        return result[0]["data"]["telegramGameTapbotStart"]

    async def claim_tap_bot(self, session: requests.AsyncSession):
        payload = [
            {
                "operationName": "TapbotClaim",
                "variables": {},
                "query": "fragment FragmentTapBotConfig on TelegramGameTapbotOutput {\n  damagePerSec\n  endsAt\n  id\n  isPurchased\n  startsAt\n  totalAttempts\n  usedAttempts\n  __typename\n}\n\nmutation TapbotClaim {\n  telegramGameTapbotClaimCoins {\n    ...FragmentTapBotConfig\n    __typename\n  }\n}",
            }
        ]
        result = await self._request(session, "POST", payload)
        return result[0]["data"]["telegramGameTapbotClaimCoins"]

    async def process_taps(
        self, session: requests.AsyncSession, taps_count: int, combo: list | None = None
    ):
        vector = ",".join(combo) if combo else self.generate_vector(taps_count)
        payload = [
            {
                "operationName": "MutationGameProcessTapsBatch",
                "variables": {
                    "payload": {
                        "nonce": self.nonce,
                        "tapsCount": taps_count,
                        "vector": vector,
                    }
                },
                "query": """mutation MutationGameProcessTapsBatch($payload: TelegramGameTapsBatchInput!) {
                            telegramGameProcessTapsBatch(payload: $payload) {
                                ...FragmentBossFightConfig
                                __typename
                            }
                        }
                        fragment FragmentBossFightConfig on TelegramGameConfigOutput {
                            _id
                            coinsAmount
                            currentEnergy
                            maxEnergy
                            weaponLevel
                            zonesCount
                            tapsReward
                            energyLimitLevel
                            energyRechargeLevel
                            tapBotLevel
                            currentBoss {
                                _id
                                level
                                currentHealth
                                maxHealth
                                __typename
                            }
                            freeBoosts {
                                _id
                                currentTurboAmount
                                maxTurboAmount
                                turboLastActivatedAt
                                turboAmountLastRechargeDate
                                currentRefillEnergyAmount
                                maxRefillEnergyAmount
                                refillEnergyLastActivatedAt
                                refillEnergyAmountLastRechargeDate
                                __typename
                            }
                            bonusLeaderDamageEndAt
                            bonusLeaderDamageStartAt
                            bonusLeaderDamageMultiplier
                            nonce
                            spinEnergyNextRechargeAt
                            spinEnergyNonRefillable
                            spinEnergyRefillable
                            spinEnergyTotal
                            spinEnergyStaticLimit
                            __typename
                        }""",
            }
        ]

        result = await self._request(session, "POST", payload)

        if result[0].get("errors"):
            raise Exception(result[0]["errors"][0]["message"])

        # print("Result is=> ", result)
        self.nonce = result[0]["data"]["telegramGameProcessTapsBatch"][
            "nonce"
        ]  # Update nonce for the next request
        return result[0]["data"]["telegramGameProcessTapsBatch"]

    async def spin_slot_machine(self, session: requests.AsyncSession, spin_count: int):
        # FIXME: Remove this, Any spin number is valid 
        # valid_spin_counts = [1, 2, 3, 5, 10, 50, 150]
        # if spin_count not in valid_spin_counts:
        #     raise ValueError("Invalid spin count")
        payload = [
            {
                "operationName": "spinSlotMachine",
                "variables": {"payload": {"spinsCount": spin_count}},
                "query": "fragment FragmentBossFightConfig on TelegramGameConfigOutput {\n    _id\n    coinsAmount\n    currentEnergy\n    maxEnergy\n    weaponLevel\n    zonesCount\n    tapsReward\n    energyLimitLevel\n    energyRechargeLevel\n    tapBotLevel\n    currentBoss {\n      _id\n      level\n      currentHealth\n      maxHealth\n    }\n    freeBoosts {\n      _id\n      currentTurboAmount\n      maxTurboAmount\n      turboLastActivatedAt\n      turboAmountLastRechargeDate\n      currentRefillEnergyAmount\n      maxRefillEnergyAmount\n      refillEnergyLastActivatedAt\n      refillEnergyAmountLastRechargeDate\n    }\n    bonusLeaderDamageEndAt\n    bonusLeaderDamageStartAt\n    bonusLeaderDamageMultiplier\n    nonce\n    spinEnergyNextRechargeAt\n    spinEnergyNonRefillable\n    spinEnergyRefillable\n    spinEnergyTotal\n    spinEnergyStaticLimit\n  }\n    mutation spinSlotMachine($payload: SlotMachineSpinInput!) {\n    slotMachineSpinV2(payload: $payload) {\n      gameConfig {\n        ...FragmentBossFightConfig\n      }\n      spinResults {\n        id\n        combination\n        rewardAmount\n        rewardType\n        questItemsFromSpin\n      }\n      spinsProcessedCount\n      previousProgressBarConfig {\n        id\n        questItem\n        status\n        requiredQuestItems\n        collectedQuestItems\n        rewardType\n        rewardAmount\n      }\n      nextProgressBarConfig {\n        id\n        questItem\n        status\n        requiredQuestItems\n        collectedQuestItems\n        rewardType\n        rewardAmount\n      }\n      progressBarReward {\n        rewardType\n        rewardAmount\n      }\n    }\n  }",
            }
        ]
        result = await self._request(session, "POST", payload)
        # print(result)
        return result[0]["data"]["slotMachineSpinV2"]

    async def activate_boost(self, session: requests.AsyncSession, boost_type: str):
        booster_type = None
        if boost_type.lower() == "turbo":
            booster_type = "Turbo"
        elif boost_type.lower() == "recharge":
            booster_type = "Recharge"
        else:
            raise ValueError("Invalid boost type")
        payload = [
            {
                "operationName": "telegramGameActivateBooster",
                "variables": {"boosterType": booster_type},
                "query": "mutation telegramGameActivateBooster($boosterType: BoosterType!) {\n  telegramGameActivateBooster(boosterType: $boosterType) {\n    ...FragmentBossFightConfig\n    __typename\n  }\n}\n\nfragment FragmentBossFightConfig on TelegramGameConfigOutput {\n  _id\n  coinsAmount\n  currentEnergy\n  maxEnergy\n  weaponLevel\n  zonesCount\n  tapsReward\n  energyLimitLevel\n  energyRechargeLevel\n  tapBotLevel\n  currentBoss {\n    _id\n    level\n    currentHealth\n    maxHealth\n    __typename\n  }\n  freeBoosts {\n    _id\n    currentTurboAmount\n    maxTurboAmount\n    turboLastActivatedAt\n    turboAmountLastRechargeDate\n    currentRefillEnergyAmount\n    maxRefillEnergyAmount\n    refillEnergyLastActivatedAt\n    refillEnergyAmountLastRechargeDate\n    __typename\n  }\n  bonusLeaderDamageEndAt\n  bonusLeaderDamageStartAt\n  bonusLeaderDamageMultiplier\n  nonce\n  spinEnergyNextRechargeAt\n  spinEnergyNonRefillable\n  spinEnergyRefillable\n  spinEnergyTotal\n  spinEnergyStaticLimit\n  __typename\n}",
            }
        ]

        result = await self._request(session, "POST", payload)
        print(result)
        if booster_type == "Turbo":
            self.max_allowed_turbo_boosts -= 1
        elif booster_type == "Recharge":
            self.max_allowed_recharge_boosts -= 1

        return result[0]["data"]["telegramGameActivateBooster"]

    async def set_next_boss(self, session: requests.AsyncSession):
        payload = [
            {
                "operationName": "telegramGameSetNextBoss",
                "variables": {},
                "query": "mutation telegramGameSetNextBoss {\n  telegramGameSetNextBoss {\n    ...FragmentBossFightConfig\n    __typename\n  }\n}\n\nfragment FragmentBossFightConfig on TelegramGameConfigOutput {\n  _id\n  coinsAmount\n  currentEnergy\n  maxEnergy\n  weaponLevel\n  zonesCount\n  tapsReward\n  energyLimitLevel\n  energyRechargeLevel\n  tapBotLevel\n  currentBoss {\n    _id\n    level\n    currentHealth\n    maxHealth\n    __typename\n  }\n  freeBoosts {\n    _id\n    currentTurboAmount\n    maxTurboAmount\n    turboLastActivatedAt\n    turboAmountLastRechargeDate\n    currentRefillEnergyAmount\n    maxRefillEnergyAmount\n    refillEnergyLastActivatedAt\n    refillEnergyAmountLastRechargeDate\n    __typename\n  }\n  bonusLeaderDamageEndAt\n  bonusLeaderDamageStartAt\n  bonusLeaderDamageMultiplier\n  nonce\n  spinEnergyNextRechargeAt\n  spinEnergyNonRefillable\n  spinEnergyRefillable\n  spinEnergyTotal\n  spinEnergyStaticLimit\n  __typename\n}",
            }
        ]

        result = await self._request(session, "POST", payload)
        return result

    def generate_daily_combo_vector(self) -> list:
        # Possible digits
        digits = ["1", "2", "3", "4"]

        # Generate all possible 4-digit sequences with repetition
        sequences = list(itertools.product(digits, repeat=4))

        # Number of sequences
        num_sequences = len(sequences)

        print(f"Number of possible sequences: {num_sequences}")

        return [sequences, num_sequences, len(digits)]

    async def handle_boss_defeated(
        self, session: requests.AsyncSession, current_boss: dict
    ):
        current_boss_level = current_boss.get("level") or 0
        current_boss_health = current_boss.get("currentHealth")
        if current_boss_health == 0:
            if current_boss_level == MAX_BOSS_LEVEL:
                logging.info("Final Boss defeated, ending game...")
                return True

            logging.info(
                f"Boss defeated, setting next boss (LVL{current_boss_level} => LVL{current_boss_level+1})..."
            )
            await self.set_next_boss(session)
        return False

    async def play_for_daily_combo(self, _combo: list | None, brute: bool = False):
        # Get possible daily combo vectors
        [combos, num_sequences, num_digits] = (
            [["".join(_combo)], 1, len(_combo)]
            if _combo and not brute
            else self.generate_daily_combo_vector()
        )
        async with requests.AsyncSession() as session:
            game_config = await self.get_game_config(session)
            damage_per_hit = game_config.get("weaponLevel") + 1

            required_energy = num_digits * damage_per_hit
            max_tries = required_energy * num_sequences

            logging.info(f"Required energy: {required_energy}")
            logging.info(f"Max tries: {max_tries}")

            current_energy = game_config.get("currentEnergy")
            recharge_per_second = game_config.get("energyRechargeLevel") + 1

            for index, combo in enumerate(combos):
                logging.info(f"Trial {index+1} of {max_tries} *** Combo: {combo}")
                # run process_taps for each combo
                result = await self.process_taps(session, num_digits, combo=combo)
                current_energy = result.get("currentEnergy")
                taps_reward = result.get("tapsReward")
                logging.info(f"Taps processed: {result}")

                if taps_reward:
                    logging.info(f"Reward: {taps_reward} *** Combo: {combo}")
                    break
                elif index != len(combos) and required_energy > current_energy:
                    # if energy is not enough, recharge
                    time_to_next_recharge = (
                        required_energy + (required_energy - current_energy)
                    ) / recharge_per_second
                    logging.info(
                        f"Energy is not enough, recharging for {time_to_next_recharge} seconds"
                    )
                    await asyncio.sleep(time_to_next_recharge)
                else:
                    # else, sleep for a while
                    await asyncio.sleep(2)

    async def handle_boost_play(self, session: requests.AsyncSession, game_config):
        current_turbo_boosts = game_config.get("freeBoosts").get("currentTurboAmount")
        current_energy = game_config.get("currentEnergy")
        current_boss = game_config.get("currentBoss")
        current_boss_health = current_boss.get("currentHealth")
        # recharge_per_second = game_config.get("energyRechargeLevel") + 1
        damage_per_hit = game_config.get("weaponLevel") + 1
        max_energy = game_config.get("maxEnergy")

        # spin_energy_total = game_config.get("spinEnergyTotal")

        max_taps = current_energy // damage_per_hit

        estimated_boost_damage = (
            TURBO_BOOST_DAMAGE_MULTIPLIER * max_taps * damage_per_hit
        )
        recharge_per_second = game_config.get("energyRechargeLevel") + 1
        
        if (
            self.max_allowed_turbo_boosts > 0
            and current_turbo_boosts >= self.max_allowed_turbo_boosts
        ):
            while self.max_allowed_turbo_boosts:
                logging.info(
                    f"Allowed turbo boosts left: {self.max_allowed_turbo_boosts}"
                )
                logging.info(f"Estimated boost damage: {estimated_boost_damage}")
                # logging.info(f"Current boss health: {current_boss_health}")
                logging.info("Boost is ready to be activated")

                # if  current energy is less than damage_per_hit(Least required energy), break
                if current_energy < damage_per_hit:
                    return
                
                result = await self.activate_boost(session, "turbo")
               
                boost_start_time = result.get("freeBoosts").get("turboLastActivatedAt")
                logging.info(f"Boost activated: {result}")

                estimated_boost_start_time = datetime.datetime.strptime(
                    boost_start_time, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                estimated_boost_end_time = (
                    estimated_boost_start_time
                    + datetime.timedelta(seconds=TURBO_BOOST_DURATION)
                )

                # when using boost, energy isn't used. so spam the process_taps function to get max damage
                while datetime.datetime.utcnow() < estimated_boost_end_time:
                    logging.info("Boost is active, spamming process_taps")
                    estimated_boost_damage = (
                        TURBO_BOOST_DAMAGE_MULTIPLIER * max_taps * damage_per_hit
                    )
                    # estimated_boss_health = current_boss_health - estimated_boost_damage
                    result = await self.process_taps(session, max_taps)
                    # logging.info(f"Tap Result: {result}")

                    current_boss = result.get("currentBoss")
                    current_boss_health = current_boss.get("currentHealth")
                    current_energy = result.get("currentEnergy")
                    damage_per_hit = result.get("weaponLevel") + 1

                    current_turbo_boosts = result.get("freeBoosts").get(
                        "currentTurboAmount"
                    )

                    max_taps = current_energy // damage_per_hit

                    logging.info(f"Current boss health: {current_boss_health}")

                    if await self.handle_boss_defeated(session, current_boss):
                        return True

                    # if current_boss_health > estimated_boss_health:
                    #     break

                    await asyncio.sleep(0.5)
                logging.info("Boost has ended")
                await asyncio.sleep(2)

                # request cool-down and wait for minimum recharge
                # if current energy < damage_per_hit or if max_taps is 0: play request fails
                # await asyncio.sleep(damage_per_hit / recharge_per_second)
                # FIXME: problematic maths
                # current_energy = current_energy + damage_per_hit * recharge_per_second
                # max_taps = current_energy // damage_per_hit
            return result
        return game_config

    async def play_game(self, taps_count: int):
        async with requests.AsyncSession() as session:
            # if spin allowed, spin
            try:
                if self.allow_spin:
                    while True:
                        logging.info(f"Spinning for {DEFAULT_SPIN_COUNT}")
                        spin_res = await self.spin_slot_machine(session, DEFAULT_SPIN_COUNT)
                        logging.info("Spin done!")
                        logging.info(spin_res.get('spinResults'))
                        await asyncio.sleep(2)
            except Exception as e:
                print("Error spinning: ", e)
            return
            while True:
                try:
                    # if tap bot enabled, run tap bot
                    if self.tap_bot:
                        await self.run_tap_bot()

                    game_config = await self.get_game_config(session)
                    game_config = await self.handle_boost_play(session, game_config)

                    if game_config is True:
                        break

                    max_energy = game_config.get("maxEnergy")
                    current_energy = game_config.get("currentEnergy")
                    current_boss = game_config.get("currentBoss")
                    current_boss_level = current_boss.get("level")
                    current_boss_health = current_boss.get("currentHealth")
                    recharge_per_second = game_config.get("energyRechargeLevel") + 1
                    damage_per_hit = game_config.get("weaponLevel") + 1

                    max_taps = current_energy // damage_per_hit

                    logging.info(f"Max energy: {max_energy}")
                    logging.info(f"Current energy: {current_energy}")
                    logging.info(f"Current boss level: {current_boss_level}")
                    logging.info(f"Current boss health: {current_boss_health}")

                    result = await self.process_taps(session, max_taps)
                    logging.info(f"Taps processed: {result}")

                    max_energy = game_config.get("maxEnergy")
                    new_current_energy = game_config.get("currentEnergy")
                    current_boss = result.get("currentBoss")
                    current_boss_health = current_boss.get("currentHealth")
                    current_recharge_boosts = result.get("freeBoosts").get(
                        "currentRefillEnergyAmount"
                    )
                    max_recharge_boosts = result.get("freeBoosts").get(
                        "maxRefillEnergyAmount"
                    )

                    if await self.handle_boss_defeated(session, current_boss):
                        break

                    if (
                        self.max_allowed_recharge_boosts > 0
                        and current_recharge_boosts < max_recharge_boosts
                    ):
                        logging.info("Recharge is ready to be activated")

                        result = await self.activate_boost(session, "recharge")
                        logging.info(f"Recharge activated: {result}")

                        self.max_allowed_recharge_boosts -= 1
                        continue

                    time_to_next_recharge = (
                        max_energy + (max_energy - new_current_energy)
                    ) / recharge_per_second

                    logging.info(
                        f"Estimated time to next recharge: {time_to_next_recharge} seconds"
                    )

                    await asyncio.sleep(time_to_next_recharge)

                except Exception as e:
                    logging.error(f"Unexpected error: {e}")
                    break

    async def run_tap_bot(self):
        async with requests.AsyncSession() as session:
            tap_bot_config = await self.get_tap_bot_config(session)
            tap_bot_id = tap_bot_config.get("id")
            total_attempts = tap_bot_config.get("totalAttempts")
            used_attempts = tap_bot_config.get("usedAttempts")
            ends_at = tap_bot_config.get("endsAt")
            # no active tap bot
            if tap_bot_id == "0" or not ends_at:
                if total_attempts == used_attempts:
                    logging.info("All tap bot attempts used, ending game session.")
                    return

                logging.info("Tap bot not purchased, buying tap bot...")
                await self.start_tap_bot(session)
                return

            # tap bot active
            logging.info("Tap bot active, checking if session ended...")
            if datetime.datetime.now() >= datetime.datetime.strptime(
                ends_at, "%Y-%m-%dT%H:%M:%S.%fZ"
            ):
                logging.info("Tap bot session ended, claiming coins...")
                await self.claim_tap_bot(session)
                return
            logging.info("Tap bot session not ended, waiting...")


def main():
    jwt_token = input("Enter your JWT token: ").strip()
    if not jwt_token:
        print("Invalid JWT token, please try again")
        exit()
    
    # prompt fpor spin
    allow_spin = False
    allow_slot_spin = input("Do you want to spin (y/n): ").strip()
    if allow_slot_spin.lower() == "y":
        allow_spin = True
    else:
        allow_spin = False

    
    initial_nonce = (
        input("Enter the initial nonce (or press Enter to use default): ").strip()
        or None
    )
    max_allowed_turbo_boosts = int(
        input("Enter the maximum number of allowed turbo boosts: ").strip() or 0
    )
    max_allowed_recharge_boosts = int(
        input("Enter the maximum number of allowed recharge boosts: ").strip() or 0
    )

    tap_bot = False
    allow_tap_bot = input("Do you want to allow tap bot? (y/n): ").strip()
    if allow_tap_bot.lower() == "y":
        tap_bot = True
    else:
        tap_bot = False

    # brute_force_combo_sequences = False
    daily_combo_sequences = (
        input("Enter the daily combo sequences e.g. 1234 (or press Enter to skip): ")
        .strip()
        .split()
    )
    if len(daily_combo_sequences) == 0:
        combo_confirm = input(
            "Would you like to run a brute force combo sequence? (y/n): "
        ).strip()
        if combo_confirm.lower() == "y":
            daily_combo_sequences = True
        else:
            print("Skipping combo sequence...")
            daily_combo_sequences = None
    elif len(daily_combo_sequences) != COMBO_SEQUENCE_LENGTH:
        print(
            f"Invalid number of sequences, please enter {COMBO_SEQUENCE_LENGTH} sequences"
        )
        exit()
    # check if valid number
    elif not all(map(lambda x: x.isdigit(), daily_combo_sequences)):
        print("Invalid number, please enter only digits")
        exit()

    memefi_game = MemefiGame(
        jwt_token,
        initial_nonce,
        max_allowed_turbo_boosts,
        max_allowed_recharge_boosts,
        tap_bot,
        allow_spin
    )

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if daily_combo_sequences:
        asyncio.run(
            memefi_game.play_for_daily_combo(
                daily_combo_sequences, brute=daily_combo_sequences == True
            )
        )

    asyncio.run(memefi_game.play_game(taps_count=MAX_TAPS_COUNT))
