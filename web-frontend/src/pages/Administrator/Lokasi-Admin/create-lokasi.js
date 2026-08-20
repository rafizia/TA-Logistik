import { useNavigate, useLocation } from 'react-router-dom'
import { Button } from '../../../components/Button'
import { Dropdown } from '../../../components/Dropdown'
import { TextField } from '../../../components/TextField'
import React, { useEffect, useState, useCallback, useRef } from 'react'
import { Loading } from '../../../components/Loading'
import { Modal } from '../../../components/Modal'
import { checkAttributeNull } from '../../../utils/utils'
import axiosAuthInstance from '../../../utils/axios-auth-instance'
import LeafletMap from '../../../components/LeafletMap'
import { useMapEvents } from 'react-leaflet'
import { BsSearch, BsGeoAlt } from 'react-icons/bs'

// Komponen untuk menangkap klik pada peta
function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng)
    }
  })
  return null
}

function CreateLokasiAdmin() {
  let navigate = useNavigate()
  const [dataCustomer, setDataCustomer] = useState([])
  const [dataDC, setDataDC] = useState([])
  const [showLoading, setShowLoading] = useState(true)

  const dc_id = localStorage.getItem('dcId')
  const userRole = localStorage.getItem('userRole')

  // State untuk peta
  const [mapCenter, setMapCenter] = useState([-6.2088, 106.8456]) // Default: Jakarta
  const [mapMarkers, setMapMarkers] = useState([])
  const [isGeocoding, setIsGeocoding] = useState(false)
  const [geocodeError, setGeocodeError] = useState(null)
  const mapKeyRef = useRef(0)

  useEffect(() => {
    if (dataCustomer.length === 0) {
      axiosAuthInstance.get('/customers?limit=1000').then((response) => {
        const customerData = response.data.data.customers.map((item) => ({
          value: item.id,
          name: item.name
        }))
        setDataCustomer(customerData)
        setShowLoading(false)
      })
    }
  }, [dataCustomer])

  useEffect(() => {
    if (dataDC.length === 0) {
      axiosAuthInstance.get('/dcs').then((response) => {
        const dcData = response.data.data.map((item) => ({
          value: item.id,
          name: item.name
        }))
        if (dc_id !== 'null' && dc_id !== null) {
          setNewLokasiData((prev) => ({
            ...prev,
            dc_id: dc_id
          }))
        } else {
          setDataDC(dcData)
        }
        setShowLoading(false)
      })
    }
  }, [dataDC, dc_id])

  const location = useLocation()
  useEffect(() => {
    if (location.state && dataCustomer.length > 0 && dataDC.length > 0) {
      const stateData = location.state
      console.log('Prefilling from AI:', stateData)

      let updatedData = { ...newLokasiData }

      if (stateData.name) updatedData.name = stateData.name
      if (stateData.address) updatedData.address = stateData.address
      if (stateData.provinsi) updatedData.provinsi = stateData.provinsi
      if (stateData.kabupaten_kota) updatedData.kabupaten_kota = stateData.kabupaten_kota
      if (stateData.kecamatan) updatedData.kecamatan = stateData.kecamatan
      if (stateData.desa_kelurahan) updatedData.desa_kelurahan = stateData.desa_kelurahan
      if (stateData.kode_pos) updatedData.kode_pos = stateData.kode_pos
      if (stateData.open_hour) updatedData.open_hour = stateData.open_hour
      if (stateData.close_hour) updatedData.close_hour = stateData.close_hour
      if (stateData.latitude) updatedData.latitude = stateData.latitude
      if (stateData.longitude) updatedData.longitude = stateData.longitude

      if (stateData.customer_id) {
        const foundCustomer = dataCustomer.find((c) => c.value === stateData.customer_id || c.name.toLowerCase().includes(String(stateData.customer_id).toLowerCase()))
        if (foundCustomer) {
          setCustomerDropdown(foundCustomer)
          updatedData.customer_id = foundCustomer.value
        }
      }

      if (stateData.dc_id) {
        const foundDC = dataDC.find((d) => d.value === stateData.dc_id || d.name.toLowerCase().includes(String(stateData.dc_id).toLowerCase()))
        if (foundDC) {
          setDCDropdown(foundDC)
          updatedData.dc_id = foundDC.value
        }
      }

      setNewLokasiData(updatedData)

      // Jika ada koordinat dari AI, langsung pin ke peta
      if (stateData.latitude && stateData.longitude) {
        const lat = parseFloat(stateData.latitude)
        const lng = parseFloat(stateData.longitude)
        setMapCenter([lat, lng])
        setMapMarkers([{ lat, lng, popup: stateData.name || 'Lokasi' }])
      }

      window.history.replaceState({}, document.title)
    }
  }, [location.state, dataCustomer, dataDC])

  //Handle Create Req
  const [isOpenConfirmation, setIsOpenConfirmation] = useState(false)
  const [isOpenError, setIsOpenError] = useState(false)
  const [isOpenSuccess, setIsOpenSuccess] = useState(false)
  const [isError, setIsError] = useState(false)
  const [customerDropdown, setCustomerDropdown] = useState(null)
  const [dcDropdown, setDCDropdown] = useState(null)

  const [newLokasiData, setNewLokasiData] = useState({
    name: null,
    latitude: null,
    longitude: null,
    address: null,
    provinsi: null,
    kabupaten_kota: null,
    kecamatan: null,
    desa_kelurahan: null,
    kode_pos: null,
    open_hour: '08:00',
    close_hour: '17:00',
    customer_id: null,
    dc_id: null
  })

  const handleInputChange = (name, value) => {
    setNewLokasiData({ ...newLokasiData, [name]: value })
  }

  // Geocoding: cari koordinat berdasarkan alamat menggunakan Nominatim dengan strategi fallback
  const handleGeocode = useCallback(async () => {
    const { address, desa_kelurahan, kecamatan, kabupaten_kota, provinsi, name } = newLokasiData

    if (!address && !name) {
      setGeocodeError('Isi minimal kolom Nama Lokasi atau Alamat Lokasi terlebih dahulu.')
      return
    }

    // Strategi pencarian bertingkat: dari paling spesifik ke paling umum
    const strategies = [
      // 1. Coba query lengkap: alamat + kelurahan + kecamatan + kota + provinsi
      [address, desa_kelurahan, kecamatan, kabupaten_kota, provinsi].filter(Boolean).join(', '),
      // 2. Coba: alamat + kota + provinsi (lewati kelurahan/kecamatan)
      [address, kabupaten_kota, provinsi].filter(Boolean).join(', '),
      // 3. Coba: nama lokasi + kota (cocok untuk landmark/toko)
      [name, kabupaten_kota, provinsi].filter(Boolean).join(', '),
      // 4. Coba: hanya alamat saja
      address,
      // 5. Coba: hanya nama lokasi
      name,
    ].filter(Boolean).filter((q, i, arr) => arr.indexOf(q) === i) // hapus duplikat

    setIsGeocoding(true)
    setGeocodeError(null)

    const nominatimSearch = async (query) => {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&countrycodes=ID&format=json&limit=1&addressdetails=1`,
        { headers: { 'Accept-Language': 'id' } }
      )
      return await res.json()
    }

    try {
      let found = null
      let successQuery = ''

      for (const query of strategies) {
        if (!query) continue
        const results = await nominatimSearch(query)
        if (results && results.length > 0) {
          found = results[0]
          successQuery = query
          break
        }
        // Delay kecil agar tidak spam ke Nominatim (rate-limit 1 req/sec)
        await new Promise(r => setTimeout(r, 300))
      }

      if (found) {
        const latNum = parseFloat(found.lat)
        const lngNum = parseFloat(found.lon)
        setMapCenter([latNum, lngNum])
        setMapMarkers([{ lat: latNum, lng: lngNum, popup: name || address || successQuery }])
        setNewLokasiData((prev) => ({ ...prev, latitude: latNum, longitude: lngNum }))
        mapKeyRef.current += 1
      } else {
        setGeocodeError('Lokasi tidak ditemukan. Coba masukkan nama tempat/landmark yang lebih umum (contoh: "Bundaran HI" bukan "Jl. MH Thamrin No. 1").')
      }
    } catch (err) {
      setGeocodeError('Gagal mencari lokasi. Periksa koneksi internet Anda.')
    } finally {
      setIsGeocoding(false)
    }
  }, [newLokasiData])

  // Klik pada peta: update lat/lng
  const handleMapClick = useCallback((lat, lng) => {
    setMapCenter([lat, lng])
    setMapMarkers([{ lat, lng, popup: newLokasiData.name || 'Lokasi baru' }])
    setNewLokasiData((prev) => ({ ...prev, latitude: lat, longitude: lng }))
  }, [newLokasiData.name])

  const handleCustomerDropdownChange = (selectedValue) => {
    setCustomerDropdown(selectedValue)
    setNewLokasiData({
      ...newLokasiData,
      customer_id: selectedValue.value
    })
  }

  const handleDCDropdownChange = (selectedValue) => {
    setDCDropdown(selectedValue)
    setNewLokasiData({
      ...newLokasiData,
      dc_id: selectedValue.value
    })
  }

  const handleSubmit = () => {
    if (
      newLokasiData.name === null ||
      newLokasiData.address === null ||
      newLokasiData.provinsi === null ||
      newLokasiData.kabupaten_kota === null ||
      newLokasiData.kecamatan === null ||
      newLokasiData.desa_kelurahan === null ||
      newLokasiData.kode_pos === null ||
      newLokasiData.open_hour === null ||
      newLokasiData.close_hour === null ||
      newLokasiData.customer_id === null ||
      newLokasiData.dc_id === null
    ) {
      setIsOpenError(true)
      setIsError(true)
    } else {
      setIsOpenConfirmation(true)
    }
  }

  const createLokasi = async (e) => {
    e.preventDefault()
    setIsOpenConfirmation(false)
    setShowLoading(true)

    const finalData = {
      ...newLokasiData,
      latitude: newLokasiData.latitude || 0,
      longitude: newLokasiData.longitude || 0,
    }

    axiosAuthInstance
      .post('/location', finalData)
      .then((response) => {
        if (response.status === 201 || response.status === 200) {
          setShowLoading(false)
          setIsOpenSuccess(true)
        }
      })
      .catch((err) => {
        setShowLoading(false)
        setIsOpenError(true)
        console.log(err)
      })
  }

  return (
    <div className="relative h-full">
      <Loading visibility={showLoading} />
      <Modal variant="primary" isOpen={isOpenConfirmation} closeModal={() => setIsOpenConfirmation(false)} title="Buat Lokasi" description="Anda yakin ingin menyimpan lokasi baru?" rightButtonText="Yakin" onClickRight={createLokasi} leftButtonText="Batal" />

      <Modal variant="primary" isOpen={isOpenSuccess} closeModal={() => setIsOpenSuccess(false)} description="Berhasil menyimpan data lokasi." rightButtonText="Selesai" onClickRight={() => navigate(userRole === 'Super' ? '/administrator/lokasi' : '/lokasi')} />
      <Modal variant="danger" isOpen={isOpenError} closeModal={() => setIsOpenError(false)} description="Gagal menyimpan data lokasi. Periksa kembali form anda." rightButtonText="Ulangi" />

      <div className={`px-[50px] py-[30px] ${showLoading ? 'hidden' : 'visible'}`}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* Kolom kiri: Form */}
          <div className="p-4 bg-white rounded-lg">
            <div className="space-y-2">
              <h4 className='ml-2'>Masukan Data Lokasi</h4>

              <TextField label="Nama Lokasi" placeholder="Toko ABC..." required={true} className="w-full" value={newLokasiData.name || ""} onChange={(e) => handleInputChange('name', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.name)} />

              {/* Alamat dengan tombol geocoding */}
              <div>
                <TextField label="Alamat Lokasi" placeholder="Jl. Raya..." required={true} className="w-full" value={newLokasiData.address || ""} onChange={(e) => handleInputChange('address', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.address)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleGeocode() }}
                />
                <button
                  type="button"
                  onClick={handleGeocode}
                  disabled={isGeocoding}
                  className="ml-2 mt-2 flex items-center gap-2 px-4 py-2 bg-[#1F54A3] text-white text-[13px] rounded-[4px] hover:bg-[#184481] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isGeocoding ? (
                    <><span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full"></span> Mencari...</>
                  ) : (
                    <>Cari Lokasi di Peta</>
                  )}
                </button>
                {geocodeError && <p className="mt-1 text-red-500 text-[12px]">{geocodeError}</p>}
              </div>

              <div className="flex gap-4">
                <div className="w-full">
                  <TextField label="Latitude" placeholder="-6.200000" className="w-full" value={newLokasiData.latitude || ""} onChange={(e) => handleInputChange('latitude', e.target.value)} />
                </div>
                <div className="w-full">
                  <TextField label="Longitude" placeholder="106.816666" className="w-full" value={newLokasiData.longitude || ""} onChange={(e) => handleInputChange('longitude', e.target.value)} />
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-full">
                  <TextField label="Kelurahan" placeholder="Kelurahan" required={true} className="w-full" value={newLokasiData.desa_kelurahan || ""} onChange={(e) => handleInputChange('desa_kelurahan', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.desa_kelurahan)} />
                </div>
                <div className="w-full">
                  <TextField label="Kecamatan" placeholder="Kecamatan" required={true} className="w-full" value={newLokasiData.kecamatan || ""} onChange={(e) => handleInputChange('kecamatan', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.kecamatan)} />
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-full">
                  <TextField label="Kabupaten/Kota" placeholder="Kota..." required={true} className="w-full" value={newLokasiData.kabupaten_kota || ""} onChange={(e) => handleInputChange('kabupaten_kota', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.kabupaten_kota)} />
                </div>
                <div className="w-full">
                  <TextField label="Provinsi" placeholder="Provinsi" required={true} className="w-full" value={newLokasiData.provinsi || ""} onChange={(e) => handleInputChange('provinsi', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.provinsi)} />
                </div>
              </div>

              <div className="w-full">
                <TextField label="Kode Pos" placeholder="12345" required={true} className="w-full" value={newLokasiData.kode_pos || ""} onChange={(e) => handleInputChange('kode_pos', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.kode_pos)} />
              </div>

              <Dropdown placeholder="Pilih Customer" label="Customer " data={dataCustomer} className="w-full" required={true} value={customerDropdown} onChange={handleCustomerDropdownChange} isError={isError && checkAttributeNull(customerDropdown)} />

              <div className="flex gap-4">
                <div className="w-full">
                  <TextField label="Jam Buka Toko" placeholder="08:00" required={true} className="w-full" value={newLokasiData.open_hour || ""} onChange={(e) => handleInputChange('open_hour', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.open_hour)} />
                </div>
                <div className="w-full">
                  <TextField label="Jam Tutup Toko" placeholder="17:00" required={true} className="w-full" value={newLokasiData.close_hour || ""} onChange={(e) => handleInputChange('close_hour', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.close_hour)} />
                </div>
              </div>

              {dc_id !== 'null' && dc_id !== null ?
                <Dropdown placeholder="Pilih DC" label="Distribution Center (DC) " data={dataDC} className="w-full" required={true} value={dc_id} onChange={handleDCDropdownChange} />
                : userRole === 'Super' ?
                  <Dropdown placeholder="Pilih DC" label="Distribution Center (DC) " data={dataDC} className="w-full" required={true} value={dcDropdown} onChange={handleDCDropdownChange} isError={isError && checkAttributeNull(dcDropdown)} />
                  : null}

            </div>
          </div>

          {/* Kolom kanan: Peta */}
          <div className="bg-white rounded-lg p-4 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <h4 className="m-0">Lokasi di Peta</h4>
            </div>
            <p className="text-[13px] text-gray-500">
              Isi alamat lalu klik <strong>Cari Lokasi di Peta</strong>, atau klik langsung pada peta untuk menentukan titik koordinat.
            </p>
            {mapMarkers.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded text-[13px] text-green-700">
                <BsGeoAlt size={13} />
                <span>Pin: {Number(newLokasiData.latitude).toFixed(6)}, {Number(newLokasiData.longitude).toFixed(6)}</span>
              </div>
            )}
            <div className="flex-1 rounded-lg overflow-hidden" style={{ minHeight: '450px' }}>
              <LeafletMap
                key={mapKeyRef.current}
                center={mapCenter}
                zoom={mapMarkers.length > 0 ? 16 : 11}
                height="100%"
                markers={mapMarkers}
              >
                <MapClickHandler onMapClick={handleMapClick} />
              </LeafletMap>
            </div>
          </div>
        </div>

        <div className="flex justify-center gap-4 pt-6">
          <Button className="text-button btn-primary-outline" label="Kembali" onClick={() => navigate(userRole === 'Super' ? '/administrator/lokasi' : '/lokasi')} />
          <Button className="text-button btn-primary" label="Simpan" onClick={handleSubmit} />
        </div>
      </div>
    </div>
  )
}

export default CreateLokasiAdmin

