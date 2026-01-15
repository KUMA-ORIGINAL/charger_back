import hashlib
import urllib.parse


def build_payment_qr_link_without_amount(account_number, box_name, client_name, door, unique_id=None):
    def build_tlv(tag, value):
        val_str = str(value)
        return f"{tag}{len(val_str):02d}{val_str}"

    def build_nested_tlv(tag, fields_list):
        """fields_list - список кортежей (tag, value) в нужном порядке"""
        content = ""
        for sub_tag, sub_value in fields_list:
            content += build_tlv(sub_tag, sub_value)
        return f"{tag}{len(content):02d}{content}"

    def sha256_hex(s):
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    qr_parts = []

    qr_parts.append(build_tlv("00", "01"))
    qr_parts.append(build_tlv("01", "12"))

    # MAI - порядок как в эталоне
    mai_fields = [
        ("00", "c2b.bakai.kg"),
        ("01", "2"),
        ("10", account_number),
        ("12", "11"),
        ("13", "12"),
    ]
    qr_parts.append(build_nested_tlv("32", mai_fields))

    qr_parts.append(build_nested_tlv("33", [("00", box_name)]))

    qr_parts.append(build_tlv("52", "6538"))
    qr_parts.append(build_tlv("53", "417"))
    qr_parts.append(build_tlv("59", client_name))
    qr_parts.append(build_tlv("34", door))
    # qr_parts.append(build_tlv("54", amount))

    # Вычисляем CRC
    qr_without_crc = "".join(qr_parts)
    qr_for_hash = qr_without_crc
    print(qr_for_hash)
    h = sha256_hex(qr_for_hash)
    crc = h[-4:].upper()

    qr_parts.append(build_tlv("63", crc))

    tlv_string = "".join(qr_parts)
    encoded_tlv = urllib.parse.quote(tlv_string, safe='')

    return "https://payqr.kg/#" + encoded_tlv


if __name__ == "__main__":
    tlv = build_payment_qr_link_without_amount(
        account_number="1240040002323627",
        box_name="BAKAIGULBOX.888",
        client_name="Получатель 1",
        door="Door1",
    )

    print("Ваш результат:")
    print(tlv)
