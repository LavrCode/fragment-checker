import requests
import logging
import argparse
import sys
import json
import random
import os
import asyncio
from bs4 import BeautifulSoup
from aiogram import Bot
from typing import List, Optional
from fake_useragent import UserAgent
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class FragmentChecker:
    def __init__(self, telegram_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.base_url = "https://fragment.com/"
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.bot = None
        self.ua = UserAgent()
        self.user_agents = [self.ua.random for _ in range(10)]
        self.current_ua_index = 0
        self.request_count = 0
        self.last_error_time = None
        
        if telegram_token:
            self.bot = Bot(token=telegram_token)
    
    def get_next_user_agent(self) -> str:
        self.request_count += 1
        
        if self.request_count % 20 == 0:
            random_index = random.randint(0, len(self.user_agents) - 1)
            self.user_agents[random_index] = self.ua.random
        
        ua = self.user_agents[self.current_ua_index]
        self.current_ua_index = (self.current_ua_index + 1) % len(self.user_agents)
        
        return ua
            
    async def check_username(self, username: str, retry_count: int = 3) -> dict:
        for attempt in range(retry_count):
            try:
                url = f"{self.base_url}?query={username}"
                headers = {"User-Agent": self.get_next_user_agent()}
                
                response = requests.get(url, headers=headers)
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Получено ограничение запросов, ожидание {retry_after} секунд")
                    self.last_error_time = datetime.now()
                    await asyncio.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                status_element = soup.find(class_=lambda x: x and ("tm-status-unavail" in x or 
                                                                  "tm-status-avail" in x or 
                                                                  "tm-status-taken" in x))
                
                result = {
                    "username": username,
                    "available": False,
                    "status": "unknown",
                    "checked_at": datetime.now().isoformat()
                }
                
                if status_element:
                    class_name = status_element.get("class", [])
                    if "tm-status-unavail" in class_name:
                        result["available"] = True
                        result["status"] = "unavailable"
                    elif "tm-status-avail" in class_name:
                        result["status"] = "available"
                    elif "tm-status-taken" in class_name:
                        result["status"] = "taken"
                
                return result
            
            except requests.RequestException as e:
                logger.error(f"Ошибка при запросе для {username} (попытка {attempt+1}/{retry_count}): {e}")
                self.last_error_time = datetime.now()
                
                if attempt == retry_count - 1:
                    return {"username": username, "available": False, "status": "error", "error": str(e), "checked_at": datetime.now().isoformat()}
                
                backoff_time = 2 ** attempt + random.uniform(0, 1)
                logger.info(f"Повторная попытка через {backoff_time:.2f} секунд...")
                await asyncio.sleep(backoff_time)
    
    async def send_telegram_message(self, message: str) -> bool:
        if not self.bot or not self.chat_id:
            logger.warning("Бот Telegram не настроен")
            return False
        
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="HTML")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в Telegram: {e}")
            return False
    
    async def process_username(self, username: str) -> dict:
        result = await self.check_username(username)
        
        if result["available"]:
            message = f"✅ {username} свободен!"
            logger.info(message)
            
            if self.bot and self.chat_id:
                await self.send_telegram_message(message)
        else:
            logger.info(f"❌ {username} недоступен (статус: {result['status']})")
            
        return result
    
    async def process_usernames(self, usernames: List[str], delay_range: tuple = (1, 3), 
                                state_file: Optional[str] = None, batch_size: int = 10) -> List[dict]:
        
        results = []
        processed_usernames = set()
        start_index = 0
        
        if state_file and os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    saved_state = json.load(f)
                    saved_results = saved_state.get("results", [])
                    processed_usernames = {r["username"] for r in saved_results if r.get("username")}
                    results = saved_results
                    
                    logger.info(f"Загружено {len(processed_usernames)} ранее проверенных юзернеймов")
            except Exception as e:
                logger.error(f"Ошибка при загрузке прогресса: {e}")
        
        usernames_to_check = [u for u in usernames if u not in processed_usernames]
        logger.info(f"Осталось проверить {len(usernames_to_check)} юзернеймов")
        
        try:
            for i, username in enumerate(usernames_to_check):
                result = await self.process_username(username)
                results.append(result)
                
                if state_file and ((i + 1) % batch_size == 0 or i == len(usernames_to_check) - 1):
                    try:
                        with open(state_file, 'w') as f:
                            json.dump({"results": results, "last_updated": datetime.now().isoformat()}, f)
                        logger.debug(f"Прогресс сохранен, обработано {i + 1}/{len(usernames_to_check)}")
                    except Exception as e:
                        logger.error(f"Ошибка при сохранении прогресса: {e}")
                
                if i < len(usernames_to_check) - 1:
                    delay = random.uniform(delay_range[0], delay_range[1])
                    logger.debug(f"Задержка перед следующим запросом: {delay:.2f} секунд")
                    await asyncio.sleep(delay)
                    
                    if self.last_error_time and (datetime.now() - self.last_error_time).total_seconds() < 60:
                        extra_delay = random.uniform(2, 5)
                        logger.info(f"Дополнительная задержка после ошибки: {extra_delay:.2f} секунд")
                        await asyncio.sleep(extra_delay)
                        
        except KeyboardInterrupt:
            logger.info("Получено прерывание, сохраняем прогресс и завершаем работу")
            if state_file:
                with open(state_file, 'w') as f:
                    json.dump({"results": results, "last_updated": datetime.now().isoformat()}, f)
                logger.info(f"Прогресс сохранен в {state_file}")
        
        return results
    
    async def close(self):
        if self.bot:
            await self.bot.session.close()

async def main():
    parser = argparse.ArgumentParser(description="Проверка доступности юзернеймов на Fragment")
    parser.add_argument("-u", "--username", help="Проверить один юзернейм")
    parser.add_argument("-f", "--file", help="Путь к файлу со списком юзернеймов (по одному на строку)")
    parser.add_argument("-t", "--token", help="Токен Telegram бота")
    parser.add_argument("-c", "--chat", help="ID чата Telegram для отправки сообщений")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="Минимальная задержка между запросами (в секундах)")
    parser.add_argument("-D", "--max-delay", type=float, default=None, help="Максимальная задержка между запросами (в секундах)")
    parser.add_argument("-s", "--state", help="Путь к файлу для сохранения/загрузки прогресса")
    parser.add_argument("-b", "--batch", type=int, default=10, help="Размер пакета для сохранения прогресса")
    
    args = parser.parse_args()
    
    if not args.username and not args.file:
        parser.error("Требуется указать юзернейм (-u) или файл со списком юзернеймов (-f)")
    
    min_delay = max(0.5, args.delay)
    max_delay = args.max_delay if args.max_delay is not None else min_delay * 2
    
    checker = FragmentChecker(telegram_token=args.token, chat_id=args.chat)
    
    usernames = []
    
    if args.username:
        usernames.append(args.username)
        
    if args.file:
        try:
            with open(args.file, 'r') as f:
                file_usernames = [line.strip() for line in f if line.strip()]
                usernames.extend(file_usernames)
        except Exception as e:
            logger.error(f"Ошибка при чтении файла: {e}")
            sys.exit(1)
    
    if not usernames:
        logger.error("Не указаны юзернеймы для проверки")
        sys.exit(1)
        
    logger.info(f"Начинаю проверку {len(usernames)} юзернеймов...")
    logger.info(f"Задержка между запросами: {min_delay}-{max_delay} секунд")
    
    if args.state:
        logger.info(f"Прогресс будет сохраняться в файл: {args.state}")
    
    try:
        results = await checker.process_usernames(
            usernames, 
            delay_range=(min_delay, max_delay), 
            state_file=args.state,
            batch_size=args.batch
        )
        
        available_count = sum(1 for r in results if r.get("available", False))
        logger.info(f"Проверка завершена. Найдено доступных юзернеймов: {available_count}/{len(usernames)}")
        
        if available_count > 0:
            available_usernames = [r["username"] for r in results if r.get("available", False)]
            logger.info(f"Доступные юзернеймы: {', '.join(available_usernames)}")
    finally:
        await checker.close()

if __name__ == "__main__":
    asyncio.run(main()) 