import cv2
import numpy as np
import os
import argparse
from scipy.optimize import curve_fit

class ImageProcessor:
    def __init__(self, command, image_folder):
        self.command = command
        self.image_folder = image_folder
        self.angle_1 = -int(command) / 2
        self.angle_2 = int(command) / 2

    def polynomial_model(x, a, b, c):
        return a * x**2 + b * x + c

    def find_intersections(x_black, y_black, x_range, y_pred):
        indices = np.where((x_black[:, None] == np.around(x_range)) & (y_black[:, None] == np.around(y_pred)))
        intersections = list(zip(x_black[indices[0]], y_black[indices[0]]))
        return intersections

    def split_image_by_line(image, a, b, c):
        above_part = np.zeros_like(image)
        below_part = np.zeros_like(image)
        rows, cols = image.shape[:2]

        for x in range(cols):
            y_on_line = int(ImageProcessor.polynomial_model(x, a, b, c))
            above_part[:y_on_line, x] = image[:y_on_line, x]
            below_part[y_on_line:, x] = image[y_on_line:, x]

        return above_part, below_part

    def rotate_left_half_image(image, angle, center):
        rows, cols = image.shape[:2]
        center_x, center_y = center
        
        diagonal = int(np.sqrt(rows**2 + cols**2))
        new_size = (diagonal, diagonal)

        left_half = image[:, :center_x]
        right_half = image[:, center_x:]

        fill_color = (255, 255, 255) if len(image.shape) == 3 else 255
        new_image = np.full((new_size[1], new_size[0]) + ((3,) if len(image.shape) == 3 else ()), fill_color, dtype=image.dtype)
        
        offset = (new_size[0] // 2 - left_half.shape[1] // 2, new_size[1] // 2 - rows // 2)
        new_image[offset[1]:offset[1] + rows, offset[0]:offset[0] + left_half.shape[1]] = left_half

        new_center = (center_x + offset[0], center_y + offset[1])
        
        M = cv2.getRotationMatrix2D(new_center, angle, 1)
        
        rotated_left_half = cv2.warpAffine(new_image, M, new_size)
        
        rotated_left_half = rotated_left_half[offset[1]:offset[1] + rows, offset[0]:offset[0] + left_half.shape[1]]
        
        if rotated_left_half.shape[0] != rows:
            rotated_left_half = cv2.resize(rotated_left_half, (rotated_left_half.shape[1], rows))
        
        rotated_image = np.hstack((rotated_left_half, right_half))
        
        return rotated_image

    def adjust_image(image, top=200, bottom=200, left=200, right=200, border_color=(255, 255, 255)):
        return cv2.copyMakeBorder(image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=border_color)

    def preprocess_image(image, threshold_value=240):
        img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        ret, thresh = cv2.threshold(img_gray, threshold_value, 255, cv2.THRESH_BINARY)
        return thresh

    def process_image(self, file):
        image_path = os.path.join(self.image_folder, file)
        I = cv2.imread(image_path)
        if I is None:
            return

        image = self.adjust_image(I)
        thresh_image = self.preprocess_image(image)

        black_pixels = np.where(thresh_image < 240)
        x_black, y_black = black_pixels[1], black_pixels[0]

        popt, _ = curve_fit(self.polynomial_model, x_black, y_black)
        a, b, c = popt

        x_range = np.linspace(x_black.min(), x_black.max(), 500)
        y_pred = self.polynomial_model(x_range, *popt)

        intersections = self.find_intersections(x_black, y_black, x_range, y_pred)
        rotation_center = sorted(intersections, key=lambda intersection: intersection[0])[0]
        rotation_center = [int(rotation_center[0]), int(rotation_center[1])]

        above_part, below_part = self.split_image_by_line(image, a, b, c)
        above_part_rotated = self.rotate_left_half_image(above_part, self.angle_1, rotation_center)
        below_part_rotated = self.rotate_left_half_image(below_part, self.angle_2, rotation_center)

        final_image = above_part_rotated + below_part_rotated

        fill_color = [255, 255, 255]
        black_pixel_mask = (final_image[:, :, :3] == [0, 0, 0]).all(axis=2)
        final_image[black_pixel_mask] = fill_color

        final_image = cv2.medianBlur(final_image, 7)

        # Save the final image in JPG format
        saved_file_name = "processed_" + file.split('.')[0] + ".jpg"
        save_path = os.path.join(self.image_folder, saved_file_name)
        cv2.imwrite(save_path, final_image)

        print(f"Image saved as: {save_path}")

    def process_images(self):
        if self.command == 0:
            print("There are no new images because the command angle is zero.")
            return

        if not (-10 < int(self.command) <= 20):
            print("Result not achievable")
            return

        image_files = os.listdir(self.image_folder)
        for file in image_files:
            self.process_image(file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process and save images.')
    parser.add_argument('command', type=int, help='The command for image rotation')
    parser.add_argument('image_folder', type=str, help='The path to the folder containing the images')

    args = parser.parse_args()

    processor = ImageProcessor(args.command, args.image_folder)
    processor.process_images()
