import { useNavigate } from 'react-router-dom'
import { Button } from '../../../components/Button'
import { Dropdown } from '../../../components/Dropdown'
import { TextField } from '../../../components/TextField'
import React, { useEffect, useState } from 'react'
import { Loading } from '../../../components/Loading'
import { Modal } from '../../../components/Modal'
import { checkAttributeNull } from '../../../utils/utils'
import axiosAuthInstance from '../../../utils/axios-auth-instance'

function CreateLokasiAdmin() {
  let navigate = useNavigate()
  const [dataPerusahaan, setDataPerusahaan] = useState([])
  const [dataDC, setDataDC] = useState([])
  const [showLoading, setShowLoading] = useState(true)

  const dc_id = localStorage.getItem('dcId')
  const userRole = localStorage.getItem('userRole')

  useEffect(() => {
    if (dataPerusahaan.length === 0) {
      axiosAuthInstance.get('/customers?limit=1000').then((response) => {
        const customerData = response.data.data.customers.map((item) => ({
          value: item.id,
          name: item.name
        }))
        setDataPerusahaan(customerData)
        setShowLoading(false)
      })
    }
  }, [dataPerusahaan])

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

  //Handle Create Req
  const [isOpenConfirmation, setIsOpenConfirmation] = useState(false)
  const [isOpenError, setIsOpenError] = useState(false)
  const [isOpenSuccess, setIsOpenSuccess] = useState(false)
  const [isError, setIsError] = useState(false)
  const [perusahaanDropdown, setPerusahaanDropdown] = useState(null)
  const [dcDropdown, setDCDropdown] = useState(null)

  const [newLokasiData, setNewLokasiData] = useState({
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

  const handlePerusahaanDropdownChange = (selectedValue) => {
    setPerusahaanDropdown(selectedValue)
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
    
    // Defaulting lat/long to 0 since no map component exists yet
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
        <div className="p-8 bg-white rounded-lg">
          <h4>Masukan Data Lokasi</h4>
          <div className="pt-4 space-y-4">
            
            <TextField label="Alamat Lokasi" placeholder="Jl. Raya..." required={true} className="w-full" value={newLokasiData.address || ""} onChange={(e) => handleInputChange('address', e.target.value)} isError={isError && checkAttributeNull(newLokasiData.address)} />

            <div className="flex gap-4">
              <div className="w-full">
                <TextField label="Latitude" placeholder="-6.200000" className="w-full" value={newLokasiData.latitude || ""} onChange={(e) => handleInputChange('latitude', e.target.value)} disabled={false} />
              </div>
              <div className="w-full">
                <TextField label="Longitude" placeholder="106.816666" className="w-full" value={newLokasiData.longitude || ""} onChange={(e) => handleInputChange('longitude', e.target.value)} disabled={false} />
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

            <Dropdown placeholder="Pilih Perusahaan" label="Perusahaan " data={dataPerusahaan} className="w-full" required={true} value={perusahaanDropdown} onChange={handlePerusahaanDropdownChange} isError={isError && checkAttributeNull(perusahaanDropdown)} />

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

        <div className="flex justify-center gap-4 pt-4">
          <Button className="text-button btn-primary-outline" label="Kembali" onClick={() => navigate(userRole === 'Super' ? '/administrator/lokasi' : '/lokasi')} />
          <Button className="text-button btn-primary" label="Simpan" onClick={handleSubmit} />
        </div>
      </div>
    </div>
  )
}

export default CreateLokasiAdmin
