#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utility function for running classifiers.

.. codeauthor:: Rasmus Handberg <rasmush@phys.au.dk>
"""

from __future__ import division, with_statement, print_function, absolute_import
import six
import numpy as np
from bottleneck import nanmedian, nansum
import matplotlib.pyplot as plt
import sqlite3
import os.path
from tqdm import tqdm
from starclass import BaseClassifier, StellarClasses

# Point this to the directory where the TDA simulations are stored
# URL: https://tasoc.dk/wg0/SimData
# The directories "sysnoise", "noisy" and "clean" should exist in this directory
INPUT_DIR = r'F:\tda_simulated_data'

#----------------------------------------------------------------------------------------------
def generate_todolist():
	# Make sure some directories exist:
	#os.makedirs(os.path.join(INPUT_DIR, 'sysnoise_by_sectors'), exist_ok=True)
	#os.makedirs(os.path.join(INPUT_DIR, 'noisy_by_sectors'), exist_ok=True)
	#os.makedirs(os.path.join(INPUT_DIR, 'clean_by_sectors'), exist_ok=True)

	sqlite_file = os.path.join(INPUT_DIR, 'todo.sqlite')
	with sqlite3.connect(sqlite_file) as conn:
		conn.row_factory = sqlite3.Row
		cursor = conn.cursor()

		cursor.execute("""CREATE TABLE todolist (
			priority BIGINT PRIMARY KEY NOT NULL,
			starid BIGINT NOT NULL,
			datasource TEXT NOT NULL DEFAULT 'ffi',
			camera INT NOT NULL,
			ccd INT NOT NULL,
			method TEXT DEFAULT NULL,
			tmag REAL,
			status INT DEFAULT NULL,
			cbv_area INT NOT NULL
		);""")

		cursor.execute("""CREATE TABLE diagnostics (
			priority BIGINT PRIMARY KEY NOT NULL,
			starid BIGINT NOT NULL,
			lightcurve TEXT,
			elaptime REAL NOT NULL,
			mean_flux DOUBLE PRECISION,
			variance DOUBLE PRECISION,
			variability DOUBLE PRECISION,
			mask_size INT,
			pos_row REAL,
			pos_column REAL,
			contamination REAL,
			stamp_resizes INT,
			errors TEXT,
			eclon DOUBLE PRECISION,
			eclat DOUBLE PRECISION
		);""")

		# Create the same indicies as is available in the real todolists:
		cursor.execute("CREATE UNIQUE INDEX priority_idx ON todolist (priority);")
		cursor.execute("CREATE INDEX starid_datasource_idx ON todolist (starid, datasource);") # FIXME: Should be "UNIQUE", but something is weird in ETE-6?!
		cursor.execute("CREATE INDEX status_idx ON todolist (status);")
		cursor.execute("CREATE INDEX starid_idx ON todolist (starid);")
		cursor.execute("CREATE INDEX variability_idx ON diagnostics (variability);")
		conn.commit()

		print("Step 1: Reading file and extracting information...")
		pri = 0
		starlist = np.genfromtxt(os.path.join(INPUT_DIR, 'Data_Batch_TDA4_r1.txt'), delimiter=',', dtype=None)
		for k, star in tqdm(enumerate(starlist), total=len(starlist)):
			#print(star)

			# Get starid:
			starname = star[0]
			if not isinstance(starname, six.string_types): starname = starname.decode("utf-8") # For Python 3
			starid = int(starname[4:])


			data_sysnoise = np.loadtxt(os.path.join(INPUT_DIR, 'sysnoise', 'Star%d.sysnoise' % starid))
			#data_noisy = np.loadtxt(os.path.join(INPUT_DIR, 'noisy', 'Star%d.noisy' % starid))
			#data_clean = np.loadtxt(os.path.join(INPUT_DIR, 'clean', 'Star%d.clean' % starid))

			# Just because Mikkel can not be trusted:
			#if star[2] == 1800:
			if (data_sysnoise[1,0] - data_sysnoise[0,0])*86400 > 1000:
				datasource = 'ffi'
			else:
				datasource = 'tpf'

			# Extract the camera from the lattitude:
			tmag = star[1]
			ecllat = star[4]
			ecllon = star[5]
			if ecllat < 6+24:
				camera = 1
			elif ecllat < 6+2*24:
				camera = 2
			elif ecllat < 6+3*24:
				camera = 3
			else:
				camera = 4

			#sector = np.floor(data_sysnoise[:,0] / 27.4) + 1
			#sectors = [int(s) for s in np.unique(sector)]
			if data_sysnoise[-1,0] - data_sysnoise[0,0] > 27.4:
				raise Exception("Okay, didn't we agree that this should be only one sector?!")

			#indx = (sector == s)
			#data_sysnoise_sector = data_sysnoise[indx, :]
			#data_noisy_sector = data_noisy[indx, :]
			#data_clean_sector = data_clean[indx, :]

			lightcurve = 'Star%d' % (starid)
			#lightcurve = 'Star%d-sector%02d' % (starid, s)

			# Save files cut up into sectors:
			#np.savetxt(os.path.join(INPUT_DIR, 'sysnoise_by_sectors', lightcurve + '.sysnoise'), data_sysnoise_sector, fmt=('%.8f', '%.18e', '%.18e', '%d'), delimiter='  ')
			#np.savetxt(os.path.join(INPUT_DIR, 'noisy_by_sectors', lightcurve + '.noisy'), data_noisy_sector, fmt=('%.8f', '%.18e', '%.18e', '%d'), delimiter='  ')
			#np.savetxt(os.path.join(INPUT_DIR, 'clean_by_sectors', lightcurve + '.clean'), data_clean_sector, fmt=('%.9f', '%.18e', '%.18e', '%d'), delimiter='  ')

			#sqlite_file = os.path.join(INPUT_DIR, 'todo-sector%02d.sqlite' % s)

			pri += 1
			mean_flux = nanmedian(data_sysnoise[:,1])
			variance = nansum((data_sysnoise[:,1] - mean_flux)**2) / (data_sysnoise.shape[0] - 1)

			# This could be done in the photometry code as well:
			time = data_sysnoise[:,0]
			flux = data_sysnoise[:,1] / mean_flux
			indx = np.isfinite(flux)
			p = np.polyfit(time[indx], flux[indx], 3)
			variability = np.nanstd(flux - np.polyval(p, time))

			elaptime = np.random.normal(3.14, 0.5)
			Npixels = np.interp(tmag, np.array([8.0, 9.0, 10.0, 12.0, 14.0, 16.0]), np.array([350.0, 200.0, 125.0, 100.0, 50.0, 40.0]))

			cursor.execute("INSERT INTO todolist (priority,starid,tmag,datasource,status,camera,ccd,cbv_area) VALUES (?,?,?,?,1,?,0,0);", (
				pri,
				starid,
				tmag,
				datasource,
				camera
			))
			cursor.execute("INSERT INTO diagnostics (priority,starid,lightcurve,elaptime,mean_flux,variance,variability,mask_size,pos_row,pos_column,contamination,stamp_resizes,eclon,eclat) VALUES (?,?,?,?,?,?,?,?,0,0,0.0,0,?,?);", (
				pri,
				starid,
				'sysnoise/' + lightcurve + '.sysnoise',
				elaptime,
				mean_flux,
				variance,
				variability,
				int(Npixels),
				ecllon,
				ecllat
			))

		print("Step 2: Figuring out where targets are on CCDs...")
		cursor.execute("SELECT MIN(eclon) AS min_eclon, MAX(eclon) AS max_eclon FROM diagnostics;")
		row = cursor.fetchone()
		eclon_min = row['min_eclon']
		eclon_max = row['max_eclon']

		cursor.execute("SELECT todolist.priority, camera, eclat, eclon FROM todolist INNER JOIN diagnostics ON todolist.priority=diagnostics.priority;")
		results = cursor.fetchall()
		for row in tqdm(results, total=len(results)):
			frac_lon = (row['eclon']-eclon_min) / (eclon_max-eclon_min)
			offset = (row['camera']-1)*24 + 6.0
			frac_lat = (row['eclat']-offset) / 24.0
			if frac_lon <= 0.5 and frac_lat <= 0.5:
				ccd = 1
			elif frac_lon > 0.5 and frac_lat <= 0.5:
				ccd = 2
			elif frac_lon <= 0.5 and frac_lat > 0.5:
				ccd = 3
			elif frac_lon > 0.5 and frac_lat > 0.5:
				ccd = 4
			else:
				raise Exception("WHAT?")

			pos_column = 4096 * frac_lon
			if pos_column > 2048: pos_column -= 2048
			pos_row = 4096 * frac_lat
			if pos_row > 2048: pos_row -= 2048

			cbv_area = 100*camera + 10*ccd
			if pos_row > 1024 and pos_column > 1024:
				cbv_area += 4
			elif pos_row > 1024 and pos_column <= 1024:
				cbv_area += 3
			elif pos_row <= 1024 and pos_column > 1024:
				cbv_area += 2
			else:
				cbv_area += 1

			cursor.execute("UPDATE todolist SET ccd=?, cbv_area=? WHERE priority=?;", (ccd, cbv_area, row['priority']))
			cursor.execute("UPDATE diagnostics SET pos_column=?, pos_row=? WHERE priority=?;", (pos_column, pos_row, row['priority']))

		conn.commit()
		cursor.close()

	print("DONE.")

#----------------------------------------------------------------------------------------------
def training_set_lightcurves():

	data = np.genfromtxt(os.path.join(INPUT_DIR, 'Data_Batch_TDA4_r1.txt'), dtype=None, delimiter=', ', usecols=(0,10))
	with BaseClassifier() as stcl:
		for row in data:
			starid = int(row[0][4:])
			fname = os.path.join(INPUT_DIR, 'sysnoise', 'Star%d.sysnoise' % starid) # # These are the lightcurves INCLUDING SYSTEMATIC NOISE
			task = {
				'starid': starid,
				'camera': None,
				'ccd': None
			}
			yield stcl.load_star(task, fname)

#----------------------------------------------------------------------------------------------
def training_set_labels():

	data = np.genfromtxt(os.path.join(INPUT_DIR, 'Data_Batch_TDA4_r1.txt'), dtype=None, delimiter=', ', usecols=(0,10))

	# Translation of Mikkel's identifiers into the broader
	# classes we have defined in StellarClasses:
	translate = {
		'Solar-like': StellarClasses.SOLARLIKE,
		'Transit': StellarClasses.TRANSIT,
		'Eclipse': StellarClasses.TRANSIT,
		'multi': StellarClasses.TRANSIT,
		'MMR': StellarClasses.TRANSIT,
		'RR Lyrae': StellarClasses.RRLYR,
		'RRab': StellarClasses.RRLYR,
		'RRc': StellarClasses.RRLYR,
		'RRd':  StellarClasses.RRLYR,
		'Cepheid': StellarClasses.CEPHEID,
		'FM': StellarClasses.CEPHEID,
		'1O': StellarClasses.CEPHEID,
		'1O2O': StellarClasses.CEPHEID,
		'FM1O': StellarClasses.CEPHEID,
		'Type II': StellarClasses.CEPHEID,
		'Anomaleous': StellarClasses.CEPHEID,
		'SPB': StellarClasses.SPB,
		'dsct': StellarClasses.DSCT,
		'bumpy': StellarClasses.DSCT, # Is this right?
		'gDor': StellarClasses.GDOR,
		'bCep': StellarClasses.BCEP,
		'roAp': StellarClasses.ROAP,
		'sdBV': StellarClasses.SDB,
		'Flare': StellarClasses.TRANSIENT,
		'Spots': StellarClasses.SPOTS,
		'LPV': StellarClasses.LPV,
		'MIRA': StellarClasses.LPV,
		'SR': StellarClasses.LPV,
		'Constant': StellarClasses.CONSTANT
	}

	# Create list of all the classes for each star:
	lookup = []
	for row in data:
		#starid = int(row[0][4:])
		labels = row[1].decode("utf-8").strip().split(';')
		lbls = []
		for lbl in labels:
			lbl = lbl.strip()
			if lbl == 'gDor+dSct hybrid' or lbl == 'dSct+gDor hybrid':
				lbls.append(StellarClasses.DSCT)
				lbls.append(StellarClasses.GDOR)
			elif lbl == 'bCep+SPB hybrid':
				lbls.append(StellarClasses.BCEP)
				lbls.append(StellarClasses.SPB)
			else:
				c = translate.get(lbl.strip())
				if c is None:
					print(lbl)
				else:
					lbls.append(c)

		lookup.append(tuple(set(lbls)))

	return tuple(lookup)

#----------------------------------------------------------------------------------------------
if __name__ == '__main__':

	todo_file = os.path.join(INPUT_DIR, 'todo.sqlite')

	# Needs to be run once
	# This basically extracts information from Mikkels simulations
	# to make them look like the output you would get from the
	# TASOC photometry pipeline.
	if not os.path.exists(todo_file):
		generate_todolist()

	# Training:
	# If we want to run the training, do the following:
	with BaseClassifier() as stcl:
		labels = training_set_labels()
		lightcurves = training_set_lightcurves()
		#stcl.train(lightcurves, labels)

	# Running:
	# When simply running the classifier on new stars:
	with sqlite3.connect(todo_file) as conn:
		conn.row_factory = sqlite3.Row
		cursor = conn.cursor()

		cursor.execute("SELECT * FROM todolist INNER JOIN diagnostics ON todolist.priority=diagnostics.priority WHERE status=1 ORDER BY todolist.priority;")

		with BaseClassifier() as stcl:

			for task in cursor.fetchall():

				# ----------------- This code would run on each worker ------------------------

				fname = os.path.join(INPUT_DIR, task['lightcurve']) # These are the lightcurves INCLUDING SYSTEMATIC NOISE
				lc, features = stcl.load_star(task, fname)

				lc.properties()

				plt.close('all')
				lc.plot()

				p = lc.flatten().remove_nans().remove_outliers().fill_gaps().periodogram()
				p.plot()

				res = stcl.classify(lc, features)

				# ----------------- This code would run on each worker ------------------------