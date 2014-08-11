#!/usr/bin/env python
# 
#	Callbox - Conversion Import Script
#
#	Copyright (c) 2014. by Way2CU, http://way2cu.com
#	Author: Mladen Mijatov
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import csv
import json
import urllib
import urllib2
import base64

from datetime import datetime, timedelta
from collections import namedtuple


# data structure used in update function
ConversionData = namedtuple(
			'ConversionData',
			[
				'call_timestamp',
				'caller_number',	# caller phone number
				'partner_number',	# receiving phone number
				'tags',				# conversion tags separated by space: 'Lead' or 'Sale'
				'value',
				'sale_date'
			]
		)


# columns in csv files
class Column:
	CALL_TIMESTAMP = 0
	CALLER_NUMBER = 1
	PARTNER_NUMBER = 2
	TAGS = 3
	VALUE = 4
	SALE_DATE = 5


def load_csv(file_name, delimiter=','):
	"""Load data from the specified file."""
	assert os.path.exists(file_name)

	headers = None
	result = []

	with open(file_name, 'r') as raw_file:
		reader = csv.reader(raw_file, delimiter=delimiter)

		for row in reader:
			if headers is not None:
				# parse dates
				call_timestamp = None
				if row[Column.CALL_TIMESTAMP] != '':
					call_timestamp = datetime.strptime(row[Column.CALL_TIMESTAMP], '%Y-%m-%d')

				sale_date = None
				if row[Column.SALE_DATE] != '':
					sale_date = datetime.strptime(row[Column.SALE_DATE], '%Y-%m-%d')

				# read row and create conversion data object
				data = ConversionData(
						call_timestamp = call_timestamp,
						caller_number = row[Column.CALLER_NUMBER],
						partner_number = row[Column.PARTNER_NUMBER],
						tags = row[Column.TAGS],
						value = row[Column.VALUE],
						sale_date = sale_date
					)

				result.append(data)

			else:
				# take headers from first row
				headers = row

	return result

def build_request(config, function, data=None, request_type='GET'):
	"""Build GET or POST request to API end point."""
	url = os.path.join(config['end_point'], function)
	encoded_data = urllib.urlencode(data) if data is not None else None

	if encoded_data is not None:
		# create request based on type
		if request_type == 'GET':
			result = urllib2.Request('{0}?{1}'.format(url, encoded_data))

		else:
			result = urllib2.Request(url, encoded_data)

	else:
		# no data provided, just create GET request
		result = urllib2.Request(url)
	
	# add authentication data to the request
	auth = base64.encodestring('{0}:{1}'.format(
											config['access_code'],
											config['secret'])
										).replace('\n', '')
	result.add_header('Authorization', 'Basic {0}'.format(auth))

	return result

def save_backup(data):
	"""Save backup data."""
	encoder = json.JSONEncoder(skipkeys=True, check_circular=True, sort_keys=True, indent=4)
	file_name = 'backup_{0}.json'.format(datetime.now().strftime('%Y-%m-%d_%H%M'))

	with open(file_name, 'w+') as raw_file:
		raw_file.write(encoder.encode(data))

def restore_backup(file_name, config):
	"""Restore previously saved backup."""
	assert os.path.exists(file_name)
	decoder = json.JSONDecoder()

	try:
		with open(file_name, 'r') as raw_file:
			data = decoder.decode(raw_file.read())

	except:
		print 'Error parsing backup file.'
		sys.exit(4)

	# restore data
	print 'Restoring backup: {0}'.format(file_name)
	for call in data:
		post_data = {
				'name': '',
				'value': 0,
				'sale_date': '',
				'conversion': 0
			}

		if 'sale' in call:
			post_data['name'] = call['sale']['name'],
			post_data['value'] = call['sale']['value'],
			post_data['sale_date'] = call['sale']['date'],
			post_data['conversion'] = 1 if call['sale']['conversion'] else 0

		sale_url = 'accounts/{0}/calls/{1}/sale.json'.format(config['agency_id'], call['id'])
		sale_request = build_request(config, sale_url, post_data, request_type='POST')

		print '\t{0} - {1}'.format(call['caller_number_format'], call['called_at'])
		stream = urllib2.urlopen(sale_request)
		sale_response = decoder.decode(stream.read())

def update_call_data(data, config):
	"""Update data on the Callbox server."""
	backup = []
	decoder = json.JSONDecoder()

	print 'Updating data...'
	for conversion in data:
		# we need timestamp for the call
		if conversion.call_timestamp is None:
			continue

		print '\t{0} - {1}'.format(
				conversion.caller_number,
				conversion.call_timestamp.strftime('%Y-%m-%d %H:%M:%S')
			)

		# prepare date range
		start_date = conversion.call_timestamp.replace(hour=0, minute=0, second=0)
		end_date = conversion.call_timestamp.replace(hour=23, minute=59, second=59)

		# find call id
		url = 'accounts/{0}/calls.json'.format(config['agency_id'])
		data = {
				'filter': conversion.caller_number,
				'start_date': start_date.strftime('%Y-%m-%d %H:%M:%S'),
				'end_date': end_date.strftime('%Y-%m-%d %H:%M:%S')
			}

		request = build_request(config, url, data)
		stream = urllib2.urlopen(request)
		response = decoder.decode(stream.read())

		if len(response['calls']) > 0:
			call = response['calls'][0]

			# backup call information
			backup.append(call)

			# post sale record
			post_data = {
					'name': conversion.tags,
					'value': conversion.value,
					'sale_date': conversion.sale_date.strftime('%Y-%m-%d'),
					'conversion': 1
				}

			sale_url = 'accounts/{0}/calls/{1}/sale.json'.format(config['agency_id'], call['id'])
			sale_request = build_request(config, sale_url, post_data, request_type='POST')
			stream = urllib2.urlopen(sale_request)

			sale_response = decoder.decode(stream.read())

	# save backup
	if len(backup) > 0:
		save_backup(backup)


if __name__ == '__main__':
	config = {
			'end_point': 'https://api.calltrackingmetrics.com/api/v1/',
			'agency_id': 0,
			'access_code': '',
			'secret': ''
		}

	# no input file specified
	if len(sys.argv) != 2:
		print 'Required input file was not specified.'
		print 'Usage:\n\t{0} conversions.csv'.format(sys.argv[0])
		sys.exit(1)

	if os.path.splitext(sys.argv[1])[1] == '.csv':
		# load data from the csv file
		try:
			data = load_csv(sys.argv[1])

		except AssertionError, error:
			# we need valid input file
			print 'Unable to load data from the specified file. {0}'.format(str(error))
			sys.exit(2)

		# send data to server
		update_call_data(data, config)

	elif os.path.splitext(sys.argv[1])[1] == '.json':
		# restore backup
		try:
			restore_backup(sys.argv[1], config)

		except AssertionError, error:
			print 'Unable to load backup from the specified file. {0}'.format(str(error))
			sys.exit(2)
