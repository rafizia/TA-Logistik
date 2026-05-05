import BaseTable, { SelectColumnFilter, StatusPill, ActionButtons } from '../../../components/BaseTable'
import React, { useEffect, useState } from 'react'
import { Button } from '../../../components/Button'
import { BsPlusLg, BsCloudUpload, BsSearch } from 'react-icons/bs'
import { useNavigate } from 'react-router-dom'
import { Loading } from '../../../components/Loading'
import axiosAuthInstance from '../../../utils/axios-auth-instance'

function ViewAllTruksAdmin() {
  const [dataTruk, setDataTruk] = useState([])
  const [showLoading, setShowLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    axiosAuthInstance
      .get('/administrator/trucks')
      .then((response) => {
        setDataTruk(response.data.data.trucks)
        setShowLoading(false)
      })
      .catch((error) => {
        console.error('Error fetching trucks:', error)
        setShowLoading(false)
      })
  }, [])

  const columns = React.useMemo(
    () => [
      {
        Header: 'Nomor Plat',
        accessor: 'plate_number',
        Filter: SelectColumnFilter,
        filter: 'includes'
      },
      {
        Header: 'Tipe Kendaraan',
        accessor: 'truck_type.name',
        filter: 'includes',
        Cell: ({ value }) => {
          if (value === 'BLIND_VAN') return <div>Blind Van</div>
          if (value === 'CDE') return <div>CDE</div>
          if (value === 'CDD') return <div>CDD</div>
          return <div>{value}</div>
        }
      },
      {
        Header: 'DC',
        accessor: 'dc.name',
        Filter: SelectColumnFilter,
        filter: 'includes'
      },
      {
        Header: () => <div className="flex justify-center items-center text-center">Status</div>,
        accessor: 'first_status',
        Cell: ({ value }) => (
          <div className="flex justify-center items-center">{StatusPill({ value, type: 'Truk' })}</div>
        )
      },
      {
        Header: 'Action',
        accessor: (row) => ['Truk', row.id],
        Cell: ActionButtons
      }
    ],
    []
  )

  return (
    <>
      <Loading visibility={showLoading} />
      <div className={`px-[50px] py-[30px] flex flex-col ${showLoading ? 'hidden' : 'visible'}`}>
        <div className="flex justify-between items-center mb-4">
          <div className="flex space-x-3">
            <Button
              className="bg-[#1F54A3] text-white hover:bg-[#184481] px-4 py-2 rounded-[4px] text-[14px] font-[500]"
              label="Buat baru"
              onClick={() => navigate('/administrator/truk/buat')}
              icon={<BsPlusLg size={14} />}
            />
            <Button
              className="bg-white border text-[#1F54A3] hover:bg-neutral-10 border-[#1F54A3] px-4 py-2 rounded-[4px] text-[14px] font-[500]"
              label="Unggah file"
              icon={<BsCloudUpload size={16} />}
            />
          </div>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <BsSearch className="text-gray-400" />
            </div>
            <input
              type="text"
              placeholder="Cari..."
              className="pl-10 pr-4 py-2 w-64 border rounded-[4px] focus:outline-none focus:ring-1 focus:ring-[#1F54A3] shadow-sm"
            />
          </div>
        </div>

        <BaseTable columns={columns} data={dataTruk} dataLength={dataTruk.length} judul="Truk" />
      </div>
    </>
  )
}

export default ViewAllTruksAdmin