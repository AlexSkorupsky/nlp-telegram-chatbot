import requests
import json
from app.settings import DIALOGFLOW_DEV_TOKEN


def make_first_upper(word):
	return word[0].upper() + word[1:len(word)]


def configure_crypto_currency_entity():
	url = 'https://api.dialogflow.com/v1'
	headers = {
		'Authorization': 'Bearer {}'.format(DIALOGFLOW_DEV_TOKEN),
		'Content-Type': 'application/json'
	}
	resp = requests.get(url + '/entities', headers=headers)

	# 0 Fiat_currency
	# 1 Cryptocurrency
	# 2 Sorting_parameters
	entity_id = resp.json()[1]['id']

	entities = []
	with open('./cmcapi/currencies.json', 'r') as f:
		data = json.load(f)
	set_of_names = set()
	for d in data:
		result = {}
		name = d
		symbol = data[d]

		if name not in set_of_names:
			set_of_names.add(name)
			# "btc": "BTC",
			# "eth": "ETH",
			# "xrp": "XRP"
			if name.lower() == symbol.lower():
				value = name.lower()
				synonyms = [symbol.lower(), symbol.upper(), make_first_upper(symbol.lower())]
			# "ripple": "XRP",
			# "bitcoin": "BTC",
			# "ethereum": "ETH"
			else:
				value = make_first_upper(name)
				synonyms = [make_first_upper(name), name.upper(), name.lower()]
				if name.lower() == "ethereum":
					synonyms.append("Ether")
					synonyms.append("ETHER")
					synonyms.append("ether")
			result['synonyms'] = synonyms
			result['value'] = value
			entities.append(result)

	resp = requests.post(url + '/entities/' + entity_id + '/entries', headers=headers, json=entities)
	print(resp.json())


def configure_count_entity():
	url = 'https://api.dialogflow.com/v1'
	headers = {
		'Authorization': 'Bearer {}'.format(DIALOGFLOW_DEV_TOKEN),
		'Content-Type': 'application/json'
	}
	resp = requests.get(url + '/entities', headers=headers)

	entity_id = resp.json()[1]['id']

	entities = []
	for i in range(1, 1001):
		result = {'synonyms': [i], 'value': str(i)}

		entities.append(result)

	print(entities)
	resp = requests.post(url + '/entities/' + entity_id + '/entries', headers=headers, json=entities)
	print(resp.json())


def update_currencies_json():
	# fixed bug: some currencies do not have symbols
	with open('./cmcapi/currencies.json', 'r') as f:
		data = json.load(f)

	result = {}
	for d in data:
		if d.lower() != data[d].lower():
			result[d.lower()] = d.lower()
		elif d.lower() == data[d].lower():
			for e in data:
				if data[d].lower() == data[e].lower() and e.lower() != data[e].lower():
					result[d.lower()] = e.lower()

	# now in "./cmcapi/currencies.json"
	with open('./cmcapi/temp.json', 'w') as fp:
		json.dump(result, fp, indent=2)
