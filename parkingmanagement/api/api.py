import frappe
from frappe import _
import random
import string
import qrcode
from PIL import Image, ImageDraw, ImageFont
import os
from frappe.utils.pdf import get_pdf
import datetime
import cv2


def generate_qrcode(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="transparent").convert("RGBA")
    return img

# -------------------------------------------------------Adding qr and qr-name to frame img----------------------------------------------------------
def add_qr_to_image(frame_img_path, qr_data, qr_name):
    frame_img = Image.open(frame_img_path)
    qr_img = generate_qrcode(qr_data)

    draw = ImageDraw.Draw(frame_img)

    font_path = os.path.join(
        frappe.get_app_path('parkingmanagement'), 
        'public','Roboto-Bold.ttf'
    )
    font_size = 200
    font = ImageFont.truetype(font_path, font_size)
    text = f'{qr_name}'
    text_position = (1600, 3650)
    text_color = (255, 255, 255)
    draw.text(text_position, text, fill=text_color, font=font)
    top_image = qr_img
    new_size = (2500, 2400)
    
    # Load the top image (QR code) you want to place
    top_image_resized = top_image.resize(new_size, Image.Resampling.LANCZOS)
    position = (600, 1120) 
    frame_img.paste(top_image_resized, position, top_image_resized.convert('RGBA'))
    if frame_img.mode in ("RGBA", "P"):
        frame_img = frame_img.convert("RGB")
    return frame_img

def save_image(frame_img, qr_name):
    images_dir = frappe.get_site_path('public', 'files', 'qr_codes')
    os.makedirs(images_dir, exist_ok=True)

    file_path = os.path.join(images_dir, f'{qr_name}.png')
    frame_img.save(file_path, format="PNG")
    return '/files/qr_codes/' + f'{qr_name}.png'

# -------------------------------------------------------Save QR Codes to PM QR Codes----------------------------------------------------------
def create_pm_qr_codes_doc(sl_no, qr_name, parking_type, file_path):
    item_info = frappe.new_doc("PM QR Codes")
    item_info.sl_no = sl_no
    item_info.qr_name = qr_name
    item_info.parking_type = parking_type
    item_info.qr_attach = file_path
    item_info.insert(ignore_permissions=True)

# ---------------------------------------------------------Creating QR Codes ------------------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def create_qr_codes(parking_type, number_of_qr_codes, start_number):
    prefix_map = {
        "Bike parking with shade": "BS",
        "Bike parking without shade": "BWS",
        "Car parking with shade": "CS",
        "Car parking without shade": "CWS"
    }

    prefix = prefix_map.get(parking_type, "Unknown")
    start_number = int(start_number) + 1
    number_of_qr_codes = int(number_of_qr_codes)

    frame_img_path = os.path.join(
        frappe.get_app_path('parkingmanagement'), 
        'public',
        f'{parking_type.lower().replace(" ", "_")}.png'
    )

    for i in range(start_number, start_number + number_of_qr_codes):
        qr_name = f"{prefix}-{i}"
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        qr_data = f"{qr_name}/{random_string}"

        frame_img = add_qr_to_image(frame_img_path, qr_data, qr_name)
        file_path = save_image(frame_img, qr_name)

        create_pm_qr_codes_doc(i, qr_name, parking_type, file_path)

    frappe.db.commit()

    return "QR Codes generated successfully."

# -------------------------------------------------------Fetching QR code and printing----------------------------------------------------------
@frappe.whitelist()
def fetch_and_print_qr_codes(parking_type, number_of_qr_codes, start_from):
    prefix_map = {
        "Bike parking with shade": {"prefix": "BS", "field": "bike_parking_with_shade"},
        "Bike parking without shade": {"prefix": "BWS", "field": "bike_parking_without_shade"},
        "Car parking with shade": {"prefix": "CS", "field": "car_parking_with_shade"},
        "Car parking without shade": {"prefix": "CWS", "field": "car_parking_without_shade"}
    }

    if parking_type not in prefix_map:
        return {'message': 'Invalid parking type.'}

    prefix = prefix_map[parking_type]["prefix"]
    field_to_update = prefix_map[parking_type]["field"]
    start_from = int(start_from) + 1
    number_of_qr_codes = int(number_of_qr_codes)

    # Fetch the last QR code for the given prefix
    last_qr_code = frappe.db.sql(f"""
        SELECT `name`, `qr_attach`, `sl_no`
        FROM `tabPM QR Codes`
        WHERE `name` LIKE '{prefix}-%'
        ORDER BY `sl_no` DESC
        LIMIT 1
    """, as_dict=True)

    last_qr_name = last_qr_code[0]['name'] if last_qr_code else '0'
    last_qr_sl_no = last_qr_code[0]['sl_no'] if last_qr_code else '0'

    # Now fetch QR codes starting from `start_from`
    qr_codes_from_start = frappe.db.sql(f"""
        SELECT `name`, `qr_attach`, `sl_no`
        FROM `tabPM QR Codes`
        WHERE `name` LIKE '{prefix}-%'
        AND `sl_no` >= {start_from}
        ORDER BY `sl_no` ASC
    """, as_dict=True)

    if len(qr_codes_from_start) < number_of_qr_codes:
        return {
            'message': f'Insufficient QR codes, there are only {last_qr_sl_no} QR codes available for {parking_type}, you are trying to print {number_of_qr_codes} qr codes starting from {start_from}. Please generate more QR codes or reduce the print quantity.'
        }

    for qr in qr_codes_from_start[:number_of_qr_codes]:
        if not frappe.db.exists("PM Printed QR Codes", qr['name']):
            doc = frappe.new_doc("PM Printed QR Codes")
            doc.qr_name = qr['name']
            doc.qr_upload = qr['qr_attach']
            doc.sl_no = qr['sl_no']
            doc.insert()

    # Update the field in "PM Print QR Codes" doctype
    new_start_from = start_from + number_of_qr_codes - 1
    frappe.db.set_value("PM Print QR Codes", None, field_to_update, new_start_from)

    frappe.db.commit()
    file_url =  generate_a4_page(qr_codes_from_start[:number_of_qr_codes], parking_type)

    return {'file_url': file_url}

# -------------------------------------------------------Generating A4 Page----------------------------------------------------------
def generate_a4_page(qr_codes, parking_type):
    # Initialize HTML content with a container div
    html_content = "<div'>"

    # Define maximum numbers of QR codes per row and per column
    max_per_row = 5
    max_per_column = 6
    qr_count = 0

    for qr in qr_codes:
        # Start a new page if the maximum per column is exceeded
        if qr_count % (max_per_row * max_per_column) == 0 and qr_count != 0:
            html_content += "<div style='page-break-before: always;'></div>"

        # New row every max_per_row QR codes
        if qr_count % max_per_row == 0:
            if qr_count != 0:
                html_content += "</div>"  # Close the previous row if it's not the first row
            html_content += "<div style='display: flex;'>"

        # QR code block with QR name in white color below the QR code image
        html_content += f"""
            <div style="text-align: center; margin-bottom : 15px; margin-right: 15px ">
                <img src="{qr['qr_attach']}" alt="QR Code" style="width: 160px; height: 200px;">
            </div>
        """

        qr_count += 1

        # Close the last row if it's the end of the row or the last QR code
        if qr_count % max_per_row == 0 or qr_count == len(qr_codes):
            html_content += "</div>"

    # Close the last page
    html_content += "</div>"

    # Generate PDF from HTML content
    pdf = get_pdf(html_content)

    # Generate a filename with date-time and parking type
    datetime_str = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f"QR-Codes-{parking_type}-{datetime_str}.pdf"

    # Set up Frappe response to download the PDF
    # frappe.local.response.filename = filename
    # frappe.local.response.filecontent = pdf
    # frappe.local.response.type = "download"

    file_path = frappe.utils.get_files_path(f'{filename}', is_private=False)
    with open(file_path, 'wb') as f:
        f.write(pdf)

    return f'/files/{filename}'


# -------------------------------------------------------Updating linked field of Printed QR codes----------------------------------------------------------
@frappe.whitelist()
def update_qr_code_linked_status(qr_name):
    # Fetch the QR code document based on the QR name
    qr_code_doc = frappe.get_doc("PM Printed QR Codes", qr_name)

    # Check if the document exists and the 'linked' field is not already set
    if qr_code_doc and qr_code_doc.linked != 1:
        qr_code_doc.linked = 1  # Update the 'linked' field to 1
        qr_code_doc.save()  # Save the document to update the field in the database
        frappe.db.commit()  # Commit the transaction to ensure the change is saved

        return {"success": True}
    else:
        return {"success": False, "message": f"{qr_name} is already linked."}
    
# -------------------------------------------------------Scanner Implementation of QR----------------------------------------------------------
# @frappe.whitelist()
# def qr_scanner():

#     cap = cv2.VideoCapture(1)
#     detector = cv2.QRCodeDetector()
#     # return detector

#     while True:
#         # Read frame from the camera
#         ret, frame = cap.read()
#         frappe.msgprint(ret)
#         return ret

#         # Detect QR codes in the frame
#         data, bbox, _ = detector.detectAndDecode(frame)

#         # If QR code detected
#         if data:
#             print("QR Code detected:", data)
#             break

#         # Display the frame
#         cv2.imshow('QR Code Scanner', frame)

#         # Break the loop if 'q' is pressed
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

#     # Release the camera and close the OpenCV windows
#     cap.release()
#     cv2.destroyAllWindows()

#     return "HI from Scanner"


@frappe.whitelist(allow_guest=True)
def process_qr_code(qr_data):
    # Process the QR code data here
    # Example: Print the QR data
    print("QR Code Data:", qr_data)
    # Perform any other actions based on the QR data
    # Example: Update a document, execute some business logic, etc.
    return "QR Code Data Received: " + qr_data

