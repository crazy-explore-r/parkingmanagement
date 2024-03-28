frappe.ui.form.on('PM Print QR Codes', {
    after_save: function(frm) {
        
        const parkingTypeMap = {
            "Bike parking with shade": { field: "bike_parking_with_shade"},
            "Bike parking without shade": { field: "bike_parking__without_shade"},
            "Car parking with shade": { field: "car_parking__with_shade"},
            "Car parking without shade": { field: "car_parking__without_shade"}
        };

        const parkingTypeDetails = parkingTypeMap[frm.doc.parking_type];
        if (!parkingTypeDetails) {
            frappe.msgprint(__('Invalid parking type.'));
            return;
        }

        // Extract start_from based on parking_type
        const currentField = parkingTypeDetails.field;
        const startFrom = parseInt(frm.doc[currentField]); // Ensure startFrom is an integer
        
        const number_of_qr_codes = parseInt(frm.doc.number_of_qr_codes);
        if (isNaN(number_of_qr_codes) || number_of_qr_codes <= 0) {
            frappe.msgprint(__("Please enter a valid number of QR codes you want to print."));
            return;
        }
	    
            frappe.call({
            method: "parkingmanagement.api.api.fetch_and_print_qr_codes",
            args: {
                parking_type: frm.doc.parking_type,
                number_of_qr_codes: number_of_qr_codes,
                start_from: frm.doc.startFrom
            },
            freeze: true,
            freeze_message: __("Fetching and printing QR Codes..."),
            callback: function(response) {
                if (response.message) {
                    if (response.message.file_url) {
                        // Trigger file download
                        const fileUrl = response.message.file_url;
                        const link = document.createElement('a');
                        link.href = fileUrl;
                        link.download = fileUrl.split('/').pop(); // Extract filename from URL
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);

                        frappe.msgprint(__("QR Codes fetched and printed successfully."));

                        const newStartFrom = startFrom + parseInt(frm.doc.number_of_qr_codes);
                        frm.set_value(currentField, `${newStartFrom}`);
                        
                    } else {
                        // Handle other messages (e.g., errors or notifications from the server)
                        frappe.msgprint(response.message);
                    }
                }
            },
            error: function(error) {
                console.error("Error:", error);
                frappe.msgprint(__("Error fetching and printing QR Codes."));
            }
        });
    }
});
