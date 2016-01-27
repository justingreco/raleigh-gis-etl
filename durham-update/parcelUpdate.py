import sys, os, arcpy, urllib2, json, datetime
path = os.path.dirname(sys.argv[0])
#local geodatabase
fgdb = "durham.gdb"
#name of the Wake SDE connection file (put in same directory as this script)
wakesde = "wake.sde"
#name of the property layer to be used as template
propertyA = "WAKE.PROPERTY_A"
#name of destination SDE connection file (put in same directory as this script)
destSde = "raleigh.sde"
#name of the resulting feature class
fcName = "DURHAM_PROPERTY"
def createGdb ():
	arcpy.env.overwriteOutput = True
	#create a new (overwrite) file geodatabase locally
	arcpy.CreateFileGDB_management(path, fgdb)
	arcpy.env.workspace = os.path.join(path, fgdb)
	#create new feature class using Wake property layer as template
	fc = arcpy.CreateFeatureclass_management(os.path.join(path, fgdb), fcName, "POLYGON", os.path.join(os.path.join(path, wakesde), propertyA), 'SAME_AS_TEMPLATE', 'SAME_AS_TEMPLATE', os.path.join(os.path.join(path, wakesde), propertyA))
	arcpy.AddIndex_management(fc, 'PIN_NUM', 'PARCEL_CONDO_PIN_NUM', 'NON_UNIQUE', 'ASCENDING');	
	arcpy.AddIndex_management(fc, 'FULL_STREET_NAME', 'PARCEL_CONDO_F_ST_N', 'NON_UNIQUE', 'ASCENDING');
	arcpy.AddIndex_management(fc, 'OWNER', 'PARCEL_CONDO_OWNER', 'NON_UNIQUE', 'ASCENDING');	
	return fc
def updateSde (fc):
	arcpy.env.workspace = os.path.join(path, destSde)
	if len(arcpy.ListFeatureClasses('*' + fcName)) == 0:
		#create new feature class in SDE if it does not exist
		print "Copying features to SDE"
		sdeFc = arcpy.FeatureClassToFeatureClass_conversion(fc, os.path.join(path, destSde), fcName)
		arcpy.AddIndex_management(sdeFc, 'PIN_NUM', 'PARCEL_CONDO_PIN_NUM', 'NON_UNIQUE', 'ASCENDING');	
		arcpy.AddIndex_management(sdeFc, 'FULL_STREET_NAME', 'PARCEL_CONDO_F_ST_N', 'NON_UNIQUE', 'ASCENDING');
		arcpy.AddIndex_management(sdeFc, 'OWNER', 'PARCEL_CONDO_OWNER', 'NON_UNIQUE', 'ASCENDING');
	else:
		#delete existing property features and replace with new property features
		print "Deleting features from SDE"
		arcpy.DeleteFeatures_management(fcName)
		print "Appending features to SDE"
		arcpy.Append_management([fc], fcName, "TEST","","")	
def formatPin (pin):
	#format Durham 12 digit PIN to match Wake 10 digit PIN
	pin = pin[:15]
	pin = str(pin[:4]) + str(pin[8:-5]) + str(pin[-4:])
	pin = pin[:10]
	return pin
def buildRow (attributes):
	pin_num = formatPin(attributes['PIN'])
	print pin_num
	owner = attributes['OWNER_NAME'].rstrip()[:101]
	addr1 = attributes['OWNER_ADDR'].rstrip()[:100]
	#combine city, state, and zip for ADDR2
	addr2 = attributes['OWCITY'].rstrip() + ', '+ attributes['OWSTA'].rstrip() + ' ' + attributes['OWZIPA'].rstrip()
	addr2 = addr2[:100]
	deed_book = attributes['DEED_BOOK'].rstrip()[:6]
	deed_page = attributes['DEED_PAGE'].rstrip()[:6]
	bldg_val = attributes['BLDG_VALUE']
	land_val = attributes['LAND_VALUE']
	total_value_assd =  attributes['TOTAL_VALU']
	site_address =  attributes['SITE_ADDRE'].rstrip().replace(' Unit OP', '')[:77] #replace extra text at end of one site_address
	city_decode = 'RALEIGH'
	totsalprice =  attributes['SALE_PRICE']
	sale_date =  attributes['DATE_SOLD']
	#convert to date format
	sale_date = datetime.datetime.strptime(str(sale_date), '%Y%m%d')
	#combine description with plat book and page
	propdesc = attributes['SUBD_DESC'].rstrip() + ' BM' + attributes['PLAT_BOOK'].rstrip() + ' -' + attributes['PLAT_PAGE'].strip()
	propdesc = propdesc[:250]
	type_use_decode = attributes['LANDUSE_DESC'].rstrip()[:20]
	exemptdesc = attributes['EXEMPT_CODE'].rstrip()[:20]
	#extract street name from site_address
	addressArr = site_address.split(' ', 1)
	full_street_name = addressArr[1][:36]
	old_parcel_number = attributes['PIN'][:16]
	#convert geometry to JSON string
	geometry = f['geometry']
	geometry['spatialReference'] = { 'wkid': 2264}
	geometry = json.dumps(geometry)
	#create row
	row = (pin_num, owner, addr1, addr2, deed_book, deed_page, bldg_val, land_val, total_value_assd, site_address, city_decode, totsalprice, sale_date, type_use_decode, propdesc, exemptdesc, full_street_name, old_parcel_number, geometry);
	return row	
fc = createGdb()
cursor = arcpy.da.InsertCursor(fc, ['PIN_NUM', 'OWNER', 'ADDR1', 'ADDR2', 'DEED_BOOK', 'DEED_PAGE', 'BLDG_VAL', 'LAND_VAL', 'TOTAL_VALUE_ASSD', 'SITE_ADDRESS', 'CITY_DECODE','TOTSALPRICE', 'SALE_DATE', 'TYPE_USE_DECODE', 'PROPDESC', 'EXEMPTDESC', 'FULL_STREET_NAME', 'OLD_PARCEL_NUMBER', 'SHAPE@JSON']);
#send request to Durham ArcGIS Server
response = urllib2.urlopen("http://gisweb2.durhamnc.gov/arcgis/rest/services/SharedMaps/Parcels/MapServer/3/query?where=SplitTaxDis+in+%28%27DR--R%27%2C%27DRWKR%27%29+or+SITE_ADDRE++in+%28%2711225+BAYBERRY+HILLS+DR%27%2C%279841+DERBTON+CT%27%29&outFields=*&returnGeometry=true&f=json")
jsonResponse = response.read()
result = json.loads(jsonResponse)
for f in result['features']:
	#insert feature into local feature class
	cursor.insertRow(buildRow(f['attributes']));
del cursor
updateSde(fc)