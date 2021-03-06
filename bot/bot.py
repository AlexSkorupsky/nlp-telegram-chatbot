from datetime import datetime

from bot import messages as msg
from bot import fmt
from cmcapi import load_currencies, get_prices, get_listing, load_entities
from app.logger import logger as default_logger
from dflow.agent import Agent
from dflow import intents
from dflow import entities
from requests.exceptions import HTTPError

from telegram.ext.filters import Filters
from telegram.ext import Updater, CommandHandler, MessageHandler


class CurrencyInfoBot:

	def __init__(self, token, df_config, logger=None):
		assert df_config is not None
		self._df_config = df_config
		
		# If passed logger is None, setup default logger.
		if not logger:
			logger = default_logger
		self._logger = logger

		# Create the Updater and pass it bot's token.
		# Make sure to set use_context=True to use the new context based callbacks.
		self._updater = Updater(token, use_context=True)

		# Get the dispatcher to register handlers.
		dp = self._updater.dispatcher

		# log all errors.
		dp.add_error_handler(self._log_error)

		self._init_handlers(dp)
		self._currencies = load_currencies()
		self._entities = load_entities()
		self._agents = {}

	def start(self):
		self._logger.info('Bot started at {}'.format(datetime.now()))

		# Start the bot.
		self._updater.start_polling()

		# Block until the user presses Ctrl-C or the process receives SIGINT,
		# SIGTERM or SIGABRT. This should be used most of the time, since
		# start_polling() is non-blocking and will stop the bot gracefully.
		self._updater.idle()

	def _init_handlers(self, dispatcher):
		# Available bot handlers, order is required!
		handlers = [
			# Handlers on different commands
			CommandHandler('start', self._start_command),
			CommandHandler('stop', self._stop_command),
			
			# Send a message when the command /help is issued.
			CommandHandler('help', self._reply(msg.HELP)),
			
			# Handlers on message
			MessageHandler(Filters.text, self._text_message),
			MessageHandler(Filters.voice, self._voice_message),
			
			# Handle all other message types.
			MessageHandler(Filters.all, self._reply(msg.INVALID))
		]

		# Setup handlers.
		for handler in handlers:
			dispatcher.add_handler(handler)

	# Wrapper to send a text message.
	@staticmethod
	def _reply(message):
		def inner(update, context):
			return update.message.reply_text(message)
		return inner

	# Sends a message when the command /start is issued.
	@staticmethod
	def _start_command(update, context):
		update.message.reply_text(msg.START)

	# Sends a message when the command /stop is issued.
	@staticmethod
	def _stop_command(update, context):
		update.message.reply_text(msg.STOP)

	# Handles the text message.
	def _text_message(self, update, context):
		input_text = update.message.text
		# Create new agent for user chat if not exists.
		chat_id = update.message['chat']['id']
		if chat_id not in self._agents:
			self._agents[chat_id] = Agent(**self._df_config)

		intent_result, intent_name = self._process_intent(input_text, chat_id)
		if intent_name == intents.QUOTES_INTENT:
			if isinstance(intent_result, dict):
				try:
					prices = self._retrieve_prices(intent_result)
					# print(prices)
					response_message = self._format_response(prices, intent_name, None)
				except HTTPError as exc:
					self._logger.warning('Unable to receive prices: {}'.format(exc))
					response_message = 'Unable to collect currencies information: {}'.format(exc)
			else:
				response_message = 'Oops, something went wrong...'
		elif intent_name == intents.LISTING_INTENT:
			if isinstance(intent_result, dict):
				try:
					listing = self._retrieve_listing(intent_result)
					response_message = self._format_response(
						listing, intent_name, intent_result[entities.SORTING_PARAMETERS]
					)
					# response_message = listing
				except HTTPError as exc:
					self._logger.warning('Unable to receive currencies list: {}'.format(exc))
					response_message = 'Unable to collect currencies list: {}'.format(exc)
			else:
				response_message = 'Oops, something went wrong...'
		else:
			response_message = intent_result

		# print(response_message)
		update.message.reply_text(response_message)

	# Handles a voice message.
	@staticmethod
	def _voice_message(update, context):
		# TODO
		update.message.reply_text('Sorry...\nVoice messages currently is not supported =(')

	# Logs errors caused by updates.
	def _log_error(self, update, context):
		self._logger.warning('Update "%s" caused error "%s"', update, context.error)
		update.message.reply_text('Oops, something went wrong...')
	
	# Normalizes inputted currencies, i.e. Bitcoin -> BTC, xrp -> XRP, etc.
	def _normalize_currencies(self, input_currencies):
		normalized = []
		for item in input_currencies:
			if item.lower() in self._currencies:
				normalized.append(self._currencies[item])
		return normalized

	def _normalize_entities(self, input_entities):
		for item in input_entities:
			if item.lower() in self._entities:
				return self._entities[item.lower()]
			else:
				return self._entities['price']
	
	# Detects intent and retrieves response message.
	# Returns dict or str.
	# If intent was detected, returns dict with crypto-currencies
	#   list and convert currency, otherwise returns str - default
	#   response from intent. Also returns intent's name.
	def _process_intent(self, text_to_analyze, chat_id):
		intent = self._agents[chat_id].detect_intent(text_to_analyze)
		
		self._logger.info('Detected intent: {}'.format(intent['name']))
		
		if intent['name'] == intents.QUOTES_INTENT or intent['name'] == intents.LISTING_INTENT:
			return intent['parameters'], intent['name']
		else:
			return intent['fulfillment_text'], intent['name']

	# Retrieves currencies prices using 'cmcapi' module.
	def _retrieve_prices(self, dict_data):
		from_currencies = self._normalize_currencies(
			list(map(lambda curr: curr.strip().lower(), dict_data[entities.CRYPTOCURRENCY]))
		)
		if isinstance(dict_data[entities.FIAT_CURRENCY], str):
			to_currency = dict_data[entities.FIAT_CURRENCY].upper()
		else:
			to_currency = dict_data[entities.FIAT_CURRENCY]

		return get_prices(from_currencies, to_currency)

	def _retrieve_listing(self, dict_data):
		limit = dict_data[entities.COUNT]
		sort = self._normalize_entities(dict_data[entities.SORTING_PARAMETERS])

		# TODO: upgrade listing by "name" parameter
		# TODO: give the user the ability to choose parameters convert(USD...) and sort_dir(desc, asc)
		return get_listing(limit, 'USD', sort, 'desc')

	@staticmethod
	def _format_response(params, intent_name, sort=None):
		if intent_name == intents.QUOTES_INTENT:
			# params -> prices
			return fmt.make_one_currency(params)
		elif intent_name == intents.LISTING_INTENT:
			# params -> currencies
			return fmt.make_currencies_top(params, sort)
		return 'Unknown format!'
