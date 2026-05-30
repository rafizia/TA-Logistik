import {
  getAllDOsAdministrator,
  getAllDOs,
  getDOslbyID,
} from "../repositories/delivery-order-repository.js";
const getAllDOAdminService = async (skip, limit) => {
  return await getAllDOsAdministrator(skip, limit);
};

const getAllDOsService = async (
  dc_id,
  skip,
  limit,
  start_date,
  end_date,
  status,
  customer_id,
  kabupaten_kota,
  so_origin,
  delivery_order_num
) => {
  return await getAllDOs(dc_id, skip, limit, start_date, end_date, status, customer_id, kabupaten_kota, so_origin, delivery_order_num);
};

const getDOByIDService = async (request) => {
  return await getDOslbyID(request);
};

export { getAllDOAdminService, getAllDOsService, getDOByIDService };
